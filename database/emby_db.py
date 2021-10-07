# -*- coding: utf-8 -*-
class EmbyDatabase:
    def __init__(self, cursor):
        self.cursor = cursor

    def get_EmbyID_by_path(self, Path):
        self.cursor.execute("SELECT emby_id FROM MediaSources WHERE Path LIKE ?", ("%%%s" % Path,))
        return self.cursor.fetchone()

    def init_EmbyDB(self):
        self.cursor.execute("CREATE TABLE IF NOT EXISTS mapping (emby_id INTEGER PRIMARY KEY, emby_folder TEXT, emby_type TEXT, kodi_type TEXT, kodi_id INTEGER, kodi_fileid INTEGER, kodi_pathid INTEGER, kodi_parent_id INTEGER, emby_parent_id TEXT, emby_presentation_key TEXT, emby_favourite BOOL)")
        self.cursor.execute("CREATE TABLE IF NOT EXISTS MediaSources (emby_id INTEGER, MediaIndex INTEGER, MediaSourceId TEXT, Path TEXT, Name TEXT, Size INTEGER)")
        self.cursor.execute("CREATE TABLE IF NOT EXISTS VideoStreams (emby_id INTEGER, MediaIndex INTEGER, StreamIndex INTEGER, Codec TEXT, BitRate INTEGER)")
        self.cursor.execute("CREATE TABLE IF NOT EXISTS AudioStreams (emby_id INTEGER, MediaIndex INTEGER, StreamIndex INTEGER, DisplayTitle TEXT)")
        self.cursor.execute("CREATE TABLE IF NOT EXISTS Subtitle (emby_id INTEGER, MediaIndex INTEGER, StreamIndex INTEGER, Codec TEXT, Language TEXT, DisplayTitle TEXT)")
        self.cursor.execute("CREATE TABLE IF NOT EXISTS RemoveItems (emby_id INTEGER PRIMARY KEY, emby_type TEXT, emby_folder TEXT)")
        self.cursor.execute("CREATE TABLE IF NOT EXISTS UpdateItems (emby_id INTEGER PRIMARY KEY, emby_folder TEXT, emby_name TEXT, emby_type TEXT)")
        self.cursor.execute("CREATE TABLE IF NOT EXISTS UserdataItems (Data TEXT)")
        self.cursor.execute("CREATE TABLE IF NOT EXISTS Whitelist (emby_folder TEXT, library_type TEXT, library_name TEXT)")
        self.cursor.execute("CREATE TABLE IF NOT EXISTS LastIncrementalSync (Type TEXT UNIQUE, Date TEXT)")
        self.cursor.execute("CREATE TABLE IF NOT EXISTS PendingSync (emby_folder TEXT, library_type TEXT, library_name TEXT, RestorePoint TEXT)")

    def remove_items_by_emby_parent_id(self, emby_parent_id, emby_folder, emby_type):
        self.cursor.execute("DELETE FROM mapping WHERE emby_parent_id = ? AND emby_type = ? AND emby_folder = ?", (emby_parent_id, emby_type, emby_folder))

    def add_Userdata(self, Data):
        self.cursor.execute("INSERT INTO UserdataItems (Data) VALUES (?)", (Data,))

    def get_Userdata(self):
        self.cursor.execute("SELECT * FROM UserdataItems")
        return self.cursor.fetchall()

    def delete_Userdata(self, Data):
        self.cursor.execute("DELETE FROM UserdataItems WHERE Data = ?", (Data,))

    def add_PendingSync(self, emby_folder, library_type, library_name, RestorePoint):
        self.cursor.execute("INSERT INTO PendingSync (emby_folder, library_type, library_name, RestorePoint) VALUES (?, ?, ?, ?)", (emby_folder, library_type, library_name, RestorePoint))

    def get_PendingSync(self):
        self.cursor.execute("SELECT * FROM PendingSync")
        return self.cursor.fetchall()

    def update_Restorepoint(self, emby_folder, library_type, library_name, RestorePoint):
        self.cursor.execute("UPDATE PendingSync SET RestorePoint = ? WHERE emby_folder = ? AND library_type = ? AND library_name = ?", (RestorePoint, emby_folder, library_type, library_name))

    def remove_PendingSync(self, emby_folder, library_type, library_name):
        self.cursor.execute("DELETE FROM PendingSync WHERE emby_folder = ? AND library_type = ? AND library_name = ?", (emby_folder, library_type, library_name))

    def remove_PendingSyncAll(self):
        self.cursor.execute("DELETE FROM PendingSync")

    def get_Libraryname_by_Id(self, emby_folder):
        self.cursor.execute("SELECT library_name FROM Whitelist WHERE emby_folder = ?", (emby_folder,))
        Data = self.cursor.fetchone()

        if Data:
            return Data[0]

        return None

    def get_Whitelist(self):
        self.cursor.execute("SELECT * FROM Whitelist")
        return self.cursor.fetchall()

    def add_Whitelist(self, emby_folder, library_type, library_name):
        self.cursor.execute("SELECT * FROM Whitelist WHERE emby_folder = ? AND library_type = ? AND library_name = ?", (emby_folder, library_type, library_name))

        if not self.cursor.fetchone():
            self.cursor.execute("INSERT INTO Whitelist (emby_folder, library_type, library_name) VALUES (?, ?, ?)", (emby_folder, library_type, library_name))

        return self.get_Whitelist()

    def remove_Whitelist(self, emby_folder, library_type, library_name):
        self.cursor.execute("DELETE FROM Whitelist WHERE emby_folder = ? AND library_type = ? AND library_name = ?", (emby_folder, library_type, library_name))
        return self.get_Whitelist()

    def get_update_LastIncrementalSync(self, LastIncrementalSync, Type):
        self.cursor.execute("SELECT * FROM LastIncrementalSync WHERE Type = ?", (Type,))
        Data = self.cursor.fetchone()
        self.cursor.execute("INSERT OR REPLACE INTO LastIncrementalSync (Type, Date) VALUES (?, ?)", (Type, LastIncrementalSync))

        if Data:
            return Data[1]

        return None

    def add_UpdateItem(self, EmbyId, LibraryId, LibraryName, emby_type):
        self.cursor.execute("INSERT OR REPLACE INTO UpdateItems (emby_id, emby_folder, emby_name, emby_type) VALUES (?, ?, ?, ?)", (EmbyId, LibraryId, LibraryName, emby_type))

    def get_UpdateItem_number_of_records(self):
        self.cursor.execute("SELECT Count(*) FROM UpdateItems")
        Data = self.cursor.fetchone()

        if Data:
            return Data[0]

        return 0

    def get_UpdateItem(self, Limit):
        self.cursor.execute("SELECT * FROM UpdateItems LIMIT %s" % Limit)
        return self.cursor.fetchall()

    def delete_UpdateItem(self, EmbyId):
        self.cursor.execute("DELETE FROM UpdateItems WHERE emby_id = ?", (EmbyId,))

    def add_RemoveItem(self, EmbyId, EmbyType, emby_folder):
        self.cursor.execute("INSERT OR REPLACE INTO RemoveItems (emby_id, emby_type, emby_folder) VALUES (?, ?, ?)", (EmbyId, EmbyType, emby_folder))

    def get_RemoveItem(self):
        self.cursor.execute("SELECT * FROM RemoveItems")
        return self.cursor.fetchall()

    def delete_RemoveItem(self, EmbyId):
        self.cursor.execute("DELETE FROM RemoveItems WHERE emby_id = ?", (EmbyId,))

    def get_item_by_emby_folder_wild(self, emby_folder):
        self.cursor.execute("SELECT emby_id, emby_type FROM mapping WHERE emby_folder LIKE ?", ("%%%s%%" % emby_folder,))
        return self.cursor.fetchall()

    def get_libraryname_by_libraryid(self, Id):
        self.cursor.execute("SELECT library_name FROM Whitelist WHERE emby_folder = ?", (Id,))
        return self.cursor.fetchone()

    def get_item_by_id(self, *args):
        self.cursor.execute("SELECT kodi_id, kodi_fileid, kodi_pathid, kodi_parent_id, kodi_type, emby_type, emby_folder, emby_parent_id, emby_presentation_key FROM mapping WHERE emby_id = ?", args)
        return self.cursor.fetchone()

    def add_reference(self, *args):
        self.cursor.execute("INSERT OR REPLACE INTO mapping (emby_id, kodi_id, kodi_fileid, kodi_pathid, emby_type, kodi_type, kodi_parent_id, emby_folder, emby_parent_id, emby_presentation_key, emby_favourite) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", args)

    def add_reference_library_id(self, emby_id, existing_emby_folder, emby_folder):
        if emby_folder not in existing_emby_folder:
            new_emby_folder = "%s;%s" % (existing_emby_folder, emby_folder)
            self.cursor.execute("UPDATE mapping SET emby_folder = ? WHERE emby_id = ?", (new_emby_folder, emby_id))

    def update_reference(self, *args):
        self.cursor.execute("UPDATE mapping SET emby_presentation_key = ?, emby_favourite = ? WHERE emby_id = ?", args)

    def update_reference_multiversion(self, emby_id, emby_presentation_key, emby_favourite, kodi_id, kodi_fileid, kodi_pathid, kodi_parentid):
        self.cursor.execute("UPDATE mapping SET emby_presentation_key = ?, emby_favourite = ?, kodi_id = ?, kodi_fileid = ?, kodi_pathid = ?, kodi_parent_id = ? WHERE emby_id = ?", (emby_presentation_key, emby_favourite, kodi_id, kodi_fileid, kodi_pathid, kodi_parentid, emby_id))

    def update_reference_userdatachanged(self, *args):
        self.cursor.execute("UPDATE mapping SET emby_favourite = ? WHERE emby_id = ?", args)

    def get_episode_fav(self):
        self.cursor.execute("SELECT kodi_id FROM mapping WHERE kodi_type = ? AND emby_favourite = ?", ("episode", "1"))
        return self.cursor.fetchall()

    def add_mediasource(self, *args):
        self.cursor.execute("INSERT OR REPLACE INTO MediaSources (emby_id, MediaIndex, MediaSourceId, Path, Name, Size) VALUES (?, ?, ?, ?, ?, ?)", args)

    def add_videostreams(self, *args):
        self.cursor.execute("INSERT OR REPLACE INTO VideoStreams (emby_id, MediaIndex, StreamIndex, Codec, BitRate) VALUES (?, ?, ?, ?, ?)", args)

    def add_audiostreams(self, *args):
        self.cursor.execute("INSERT OR REPLACE INTO AudioStreams (emby_id, MediaIndex, StreamIndex, DisplayTitle) VALUES (?, ?, ?, ?)", args)

    def add_subtitles(self, *args):
        self.cursor.execute("INSERT OR REPLACE INTO Subtitle (emby_id, MediaIndex, StreamIndex, Codec, Language, DisplayTitle) VALUES (?, ?, ?, ?, ?, ?)", args)

    def update_parent_id(self, *args):
        self.cursor.execute("UPDATE mapping SET kodi_parent_id = ? WHERE emby_id = ?", args)

    def get_item_id_by_parent_id(self, *args):
        self.cursor.execute("SELECT emby_id, kodi_id FROM mapping WHERE kodi_parent_id = ? AND kodi_type = ?", args)
        return self.cursor.fetchall()

    def get_item_by_parent_id(self, *args):
        self.cursor.execute("SELECT emby_id, kodi_id, kodi_fileid FROM mapping WHERE kodi_parent_id = ? AND kodi_type = ?", args)
        return self.cursor.fetchall()

    def get_item_by_wild_id(self, item_id):
        self.cursor.execute("SELECT kodi_id, kodi_type FROM mapping WHERE emby_id LIKE ?", ("%s%%" % item_id,))
        return self.cursor.fetchall()

    def get_full_item_by_kodi_id(self, *args):
        self.cursor.execute("SELECT emby_id, kodi_parent_id, emby_folder, emby_type, emby_favourite FROM mapping WHERE kodi_id = ? AND kodi_type = ?", args)
        return self.cursor.fetchone()

    def get_full_item_by_kodi_id_complete(self, *args):
        self.cursor.execute("SELECT * FROM mapping WHERE kodi_id = ? AND kodi_type = ?", args)
        return self.cursor.fetchone()

    def get_media_by_id(self, *args):
        self.cursor.execute("SELECT emby_type FROM mapping WHERE emby_id = ?", args)
        Data = self.cursor.fetchone()

        if Data:
            return Data[0]

        return None

    def get_media_by_parent_id(self, *args):
        self.cursor.execute("SELECT emby_id, emby_type, kodi_id, kodi_fileid FROM mapping WHERE emby_parent_id = ?", args)
        return self.cursor.fetchall()

    def get_special_features(self, *args):
        self.cursor.execute("SELECT emby_id FROM mapping WHERE emby_type = 'SpecialFeature' AND emby_parent_id = ?", args)
        return self.cursor.fetchall()

    def get_videostreams(self, *args):
        self.cursor.execute("SELECT * FROM VideoStreams WHERE emby_id = ? AND MediaIndex = ?", args)
        return self.cursor.fetchall()

    def get_mediasource(self, *args):
        self.cursor.execute("SELECT * FROM MediaSources WHERE emby_id = ?", args)
        return self.cursor.fetchall()

    def get_kodiid(self, *args):
        self.cursor.execute("SELECT kodi_id, emby_presentation_key, kodi_fileid FROM mapping WHERE emby_id = ?", args)
        return self.cursor.fetchone()

    def get_AudioStreams(self, *args):
        self.cursor.execute("SELECT * FROM AudioStreams WHERE emby_id = ? AND MediaIndex = ?", args)
        return self.cursor.fetchall()

    def get_Subtitles(self, *args):
        self.cursor.execute("SELECT * FROM Subtitle WHERE emby_id = ? AND MediaIndex = ?", args)
        return self.cursor.fetchall()

    def remove_item(self, Id):
        self.cursor.execute("DELETE FROM mapping WHERE emby_id = ?", (Id,))
        self.remove_item_streaminfos(Id)

    def remove_item_music(self, *args):
        self.cursor.execute("DELETE FROM mapping WHERE emby_id = ?", args)

    def remove_item_music_by_libraryId(self, emby_id, LibraryId):
        self.cursor.execute("SELECT emby_folder FROM mapping WHERE emby_id = ?", (emby_id,))
        Data = self.cursor.fetchone()

        if not Data:
            return

        LibraryInfos = Data[0].split(";")
        NewLibraryInfo = ""

        for LibraryInfo in LibraryInfos:
            if LibraryInfo and LibraryId not in LibraryInfo:
                NewLibraryInfo = "%s%s;" % (NewLibraryInfo, LibraryInfo)

        if not NewLibraryInfo:
            self.cursor.execute("DELETE FROM mapping WHERE emby_id = ?", (emby_id,))
        else:
            NewLibraryInfo = NewLibraryInfo[:-1]  # remove trailing ";"
            self.cursor.execute("UPDATE mapping SET emby_folder = ? WHERE emby_id = ?", (NewLibraryInfo, emby_id))

    def remove_item_streaminfos(self, Id):
        self.cursor.execute("DELETE FROM MediaSources WHERE emby_id = ?", (Id,))
        self.cursor.execute("DELETE FROM VideoStreams WHERE emby_id = ?", (Id,))
        self.cursor.execute("DELETE FROM AudioStreams WHERE emby_id = ?", (Id,))
        self.cursor.execute("DELETE FROM Subtitle WHERE emby_id = ?", (Id,))

    def remove_items_by_parent_id(self, *args):
        self.cursor.execute("DELETE FROM mapping WHERE kodi_parent_id = ? AND kodi_type = ?", args)

    def remove_wild_item(self, item_id):
        self.cursor.execute("DELETE FROM mapping WHERE emby_id LIKE ?", ("%s%%" % item_id,))

    def get_items_by_media(self, *args):
        self.cursor.execute("SELECT emby_id FROM mapping WHERE kodi_type = ? AND emby_folder = ?", args)
        return self.cursor.fetchall()

    def get_items_by_embyparentid(self, emby_parent_id, emby_folder, emby_type):
        self.cursor.execute("SELECT * FROM mapping WHERE emby_parent_id = ? AND emby_type = ? AND emby_folder = ?", (emby_parent_id, emby_type, emby_folder))
        Data = self.cursor.fetchall()

        if Data:
            return Data

        return {}

    def get_stacked_kodiid(self, emby_presentation_key, emby_folder, emby_type):
        self.cursor.execute("SELECT kodi_id FROM mapping WHERE emby_presentation_key = ? AND emby_type = ? AND emby_folder = ?", (emby_presentation_key, emby_type, emby_folder))
        Data = self.cursor.fetchone()

        if Data:
            return Data[0]

        return None

    def check_stacked(self, emby_presentation_key, emby_folder, emby_type):
        self.cursor.execute("SELECT * FROM mapping WHERE emby_presentation_key = ? AND emby_type = ? AND emby_folder = ?", (emby_presentation_key, emby_type, emby_folder))
        Data = self.cursor.fetchall()

        if len(Data) > 1:
            return True

        return False

    def get_stacked_embyid(self, emby_presentation_key, emby_folder, emby_type):
        self.cursor.execute("SELECT emby_id FROM mapping WHERE emby_presentation_key = ? AND emby_type = ? AND emby_folder = ?", (emby_presentation_key, emby_type, emby_folder))
        Data = self.cursor.fetchall()

        if Data:
            return Data

        return None

# -*- coding: utf-8 -*-
import json
import os
import sqlite3

import xbmc
import xbmcvfs
import xbmcgui

import core.obj_ops
import helper.loghandler
from . import emby_db

LOG = helper.loghandler.LOG('EMBY.database.database')

class Database():
    timeout = 120
    discovered = False
    discovered_file = None

    #file: emby, texture, music, video, :memory: or path to file
    def __init__(self, Utils, fileID, commit_close):
        self.Utils = Utils
        self.db_file = fileID
        self.commit_close = commit_close
        self.objects = core.obj_ops.Objects(self.Utils)
        self.path = None
        self.conn = None
        self.cursor = None

    #Open the connection and return the Database class.
    #This is to allow for the cursor, conn and others to be accessible.
    def __enter__(self):
        self.path = self._sql(self.db_file)

        if not self.path:
            return

        self.conn = sqlite3.connect(self.path, timeout=self.timeout)
        self.cursor = self.conn.cursor()

        if self.db_file in ('video', 'music', 'texture', 'emby'):
            self.conn.execute("PRAGMA journal_mode=WAL") # to avoid writing conflict with kodi

        LOG.debug("--->[ database: %s ] %s" % (self.db_file, id(self.conn)))
        return self

    def _get_database(self, path, silent):
        path = self.Utils.translatePath(path)

        if not silent:
            if not xbmcvfs.exists(path):
                LOG.error("Database: %s missing" % path)
                return False

            conn = sqlite3.connect(path)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = cursor.fetchall()
            conn.close()

            if not len(tables):
                LOG.error("Database: %s malformed?" % path)
                return False

        return path

    def _sql(self, DBFile):
        databases = self.objects.objects

        if DBFile not in ('video', 'music', 'texture') or databases.get('database_set%s' % DBFile):
            return self._get_database(databases[DBFile], True)

        #Read Database from filesystem
        folder = self.Utils.translatePath("special://database/")
        _, files = xbmcvfs.listdir(folder)
        DBIDs = {
            'Textures': "texture",
            'MyMusic': "music",
            'MyVideos': "video"
        }

        Version = 0

        for DBID in DBIDs:
            key = DBIDs[DBID]

            if key == DBFile:
                for Filename in files:
                    if (Filename.startswith(DBID) and not Filename.endswith('-wal') and not Filename.endswith('-shm') and not Filename.endswith('db-journal')):
                        Temp = int(''.join(i for i in Filename if i.isdigit()))

                        if Temp > Version:
                            databases[key] = os.path.join(folder, Filename)
                            databases['database_set%s' % key] = True
                            Version = Temp

        self.Utils.window('kodidbversion.' + DBFile, str(Version))
        return databases[DBFile]

    #Close the connection and cursor
    def __exit__(self, exc_type, exc_val, exc_tb):
        changes = self.conn.total_changes

        if exc_type is not None: # errors raised
            LOG.error("type: %s value: %s" % (exc_type, exc_val))

        if self.commit_close and changes:
            LOG.info("[%s] %s rows updated." % (self.db_file, changes))
            self.conn.commit()

        LOG.debug("---<[ database: %s ] %s" % (self.db_file, id(self.conn)))
        self.cursor.close()
        self.conn.close()


#Open the databases to test if the file exists
def test_databases(Utils):
    with Database(Utils, 'video', True):
        with Database(Utils, 'music', True):
            pass

    with Database(Utils, 'emby', True) as embydb:
        emby_tables(embydb.cursor)


#Create the tables for the emby database
def emby_tables(cursor):
    cursor.execute("CREATE TABLE IF NOT EXISTS emby(emby_id TEXT UNIQUE, media_folder TEXT, emby_type TEXT, media_type TEXT, kodi_id INTEGER, kodi_fileid INTEGER, kodi_pathid INTEGER, parent_id INTEGER, checksum INTEGER, emby_parent_id TEXT)")
    cursor.execute("CREATE TABLE IF NOT EXISTS view(view_id TEXT UNIQUE, view_name TEXT, media_type TEXT)")
    cursor.execute("CREATE TABLE IF NOT EXISTS MediaSources(emby_id TEXT, MediaIndex INTEGER, Protocol TEXT, MediaSourceId TEXT, Path TEXT, Type TEXT, Container TEXT, Size INTEGER, Name TEXT, IsRemote TEXT, RunTimeTicks INTEGER, SupportsTranscoding TEXT, SupportsDirectStream TEXT, SupportsDirectPlay TEXT, IsInfiniteStream TEXT, RequiresOpening TEXT, RequiresClosing TEXT, RequiresLooping TEXT, SupportsProbing TEXT, Formats TEXT, Bitrate INTEGER, RequiredHttpHeaders TEXT, ReadAtNativeFramerate TEXT, DefaultAudioStreamIndex INTEGER)")
    cursor.execute("CREATE TABLE IF NOT EXISTS VideoStreams(emby_id TEXT, MediaIndex INTEGER, VideoIndex INTEGER, Codec TEXT, TimeBase TEXT, CodecTimeBase TEXT, VideoRange TEXT, DisplayTitle TEXT, IsInterlaced TEXT, BitRate INTEGER, BitDepth INTEGER, RefFrames INTEGER, IsDefault TEXT, IsForced TEXT, Height INTEGER, Width INTEGER, AverageFrameRate INTEGER, RealFrameRate INTEGER, Profile TEXT, Type TEXT, AspectRatio TEXT, IsExternal TEXT, IsTextSubtitleStream TEXT, SupportsExternalStream TEXT, Protocol TEXT, PixelFormat TEXT, Level INTEGER, IsAnamorphic TEXT, StreamIndex INTEGER)")
    cursor.execute("CREATE TABLE IF NOT EXISTS AudioStreams(emby_id TEXT, MediaIndex INTEGER, AudioIndex INTEGER, Codec TEXT, Language TEXT, TimeBase TEXT, CodecTimeBase TEXT, DisplayTitle TEXT, DisplayLanguage TEXT, IsInterlaced TEXT, ChannelLayout TEXT, BitRate INTEGER, Channels INTEGER, SampleRate INTEGER, IsDefault TEXT, IsForced TEXT, Profile TEXT, Type TEXT, IsExternal TEXT, IsTextSubtitleStream TEXT, SupportsExternalStream TEXT, Protocol TEXT, StreamIndex INTEGER)")
    cursor.execute("CREATE TABLE IF NOT EXISTS Subtitle(emby_id TEXT, MediaIndex INTEGER, SubtitleIndex INTEGER, Codec TEXT, Language TEXT, TimeBase TEXT, CodecTimeBase TEXT, DisplayTitle TEXT, DisplayLanguage TEXT, IsInterlaced TEXT, IsDefault TEXT, IsForced TEXT, Path TEXT, Type TEXT, IsExternal TEXT, IsTextSubtitleStream TEXT, SupportsExternalStream TEXT, Protocol TEXT, StreamIndex INTEGER)")

    columns = cursor.execute("SELECT * FROM VideoStreams")
    descriptions = [description[0] for description in columns.description]

    if 'StreamIndex' not in descriptions:
        LOG.info("Add missing column VideoStreams -> StreamIndex")
        cursor.execute("ALTER TABLE VideoStreams ADD COLUMN StreamIndex 'INTEGER'")

    columns = cursor.execute("SELECT * FROM AudioStreams")
    descriptions = [description[0] for description in columns.description]

    if 'StreamIndex' not in descriptions:
        LOG.info("Add missing column AudioStreams -> StreamIndex")
        cursor.execute("ALTER TABLE AudioStreams ADD COLUMN StreamIndex 'INTEGER'")

    columns = cursor.execute("SELECT * FROM Subtitle")
    descriptions = [description[0] for description in columns.description]

    if 'StreamIndex' not in descriptions:
        LOG.info("Add missing column Subtitle -> StreamIndex")
        cursor.execute("ALTER TABLE Subtitle ADD COLUMN StreamIndex 'INTEGER'")

    columns = cursor.execute("SELECT * FROM emby")
    descriptions = [description[0] for description in columns.description]

    if 'emby_parent_id' not in descriptions:
        LOG.info("Add missing column emby_parent_id")
        cursor.execute("ALTER TABLE emby ADD COLUMN emby_parent_id 'TEXT'")

    if 'presentation_key' not in descriptions:
        LOG.info("Add missing column presentation_key")
        cursor.execute("ALTER TABLE emby ADD COLUMN presentation_key 'TEXT'")

#Reset both the emby database and the kodi database.
def reset(Utils, Force):
#    views = emby.views.Views(Utils)

    if not Force:
        if not Utils.dialog("yesno", heading="{emby}", line1=Utils.Translate(33074)):
            return

    Utils.window('emby.shouldstop.bool', True)

    if xbmc.Monitor().waitForAbort(5):
        return

    reset_kodi(Utils)
    reset_emby(Utils)
#    views.delete_playlists()
#    views.delete_nodes()

    if Utils.dialog("yesno", heading="{emby}", line1=Utils.Translate(33086)):
        reset_artwork(Utils)

    addon_data = Utils.translatePath("special://profile/addon_data/plugin.video.emby-next-gen/")

    if Utils.dialog("yesno", heading="{emby}", line1=Utils.Translate(33087)):
        xbmcvfs.delete(os.path.join(addon_data, "settings.xml"))
        xbmcvfs.delete(os.path.join(addon_data, "data.json"))
        LOG.info("[ reset settings ]")

    if xbmcvfs.exists(os.path.join(addon_data, "sync.json")):
        xbmcvfs.delete(os.path.join(addon_data, "sync.json"))

    Utils.settings('enableMusic.bool', False)
    Utils.settings('MinimumSetup', "")
    Utils.settings('MusicRescan.bool', False)
    Utils.settings('SyncInstallRunDone.bool', False)
    Utils.settings('Migrate.bool', True)
    Utils.dialog("ok", heading="{emby}", line1=Utils.Translate(33088))
    xbmc.executebuiltin('RestartApp')

def reset_kodi(Utils):
    Progress = xbmcgui.DialogProgressBG()
    Progress.create(Utils.Translate('addon_name'), "Delete Kodi-Video Database")

    with Database(Utils, 'video', True) as videodb:
        videodb.cursor.execute("SELECT tbl_name FROM sqlite_master WHERE type='table'")
        tables = videodb.cursor.fetchall()
        Counter = 0
        Increment = 100.0 / (len(tables) - 1)

        for table in tables:
            name = table[0]

            if name != 'version':
                Counter += 1
                Progress.update(int(Counter * Increment), message="Delete Kodi-Video Database: " + name)
                videodb.cursor.execute("DELETE FROM " + name)

        Progress.close()

    with Database(Utils, 'music', True) as musicdb:
        musicdb.cursor.execute("SELECT tbl_name FROM sqlite_master WHERE type='table'")
        Progress = xbmcgui.DialogProgressBG()
        Progress.create(Utils.Translate('addon_name'), "Delete Kodi-Music Database")
        tables = musicdb.cursor.fetchall()
        Counter = 0
        Increment = 100.0 / (len(tables) - 1)

        for table in tables:
            name = table[0]

            if name != 'version':
                Counter += 1
                Progress.update(int(Counter * Increment), message="Delete Kodi-Music Database: " + name)
                musicdb.cursor.execute("DELETE FROM " + name)

        Progress.close()

    LOG.warning("[ reset kodi ]")

def reset_emby(Utils):
    Progress = xbmcgui.DialogProgressBG()
    Progress.create(Utils.Translate('addon_name'), "Delete Emby Database")

    with Database(Utils, 'emby', True) as embydb:
        embydb.cursor.execute("SELECT tbl_name FROM sqlite_master WHERE type='table'")
        tables = embydb.cursor.fetchall()
        Counter = 0
        Increment = 100.0 / (len(tables) - 2)

        for table in tables:
            name = table[0]

            if name not in ('emby', 'view'):
                Counter += 1
                Progress.update(int(Counter * Increment), message="Delete Emby Database: " + name)
                embydb.cursor.execute("DELETE FROM " + name)

            embydb.cursor.execute("DROP table IF EXISTS emby")
            embydb.cursor.execute("DROP table IF EXISTS view")

        Progress.close()

    LOG.warning("[ reset emby ]")

#Remove all existing texture
def reset_artwork(Utils):
    thumbnails = Utils.translatePath('special://thumbnails/')

    if xbmcvfs.exists(thumbnails):
        dirs, _ = xbmcvfs.listdir(thumbnails)

        for directory in dirs:
            _, thumbs = xbmcvfs.listdir(os.path.join(thumbnails, directory))
            Progress = xbmcgui.DialogProgressBG()
            Progress.create(Utils.Translate('addon_name'), "Delete Artwork Files: " + directory)
            Counter = 0
            ThumbsLen = len(thumbs)
            Increment = 0.0

            if ThumbsLen > 0:
                Increment = 100.0 / ThumbsLen

            for thumb in thumbs:
                Counter += 1
                Progress.update(int(Counter * Increment), message="Delete Artwork Files: " + directory + " / " + thumb)
                LOG.debug("DELETE thumbnail %s" % thumb)
                xbmcvfs.delete(os.path.join(thumbnails, directory, thumb))

            Progress.close()

    Progress = xbmcgui.DialogProgressBG()
    Progress.create(Utils.Translate('addon_name'), "Delete Texture Database")

    with Database(Utils, 'texture', True) as texdb:
        texdb.cursor.execute("SELECT tbl_name FROM sqlite_master WHERE type='table'")
        tables = texdb.cursor.fetchall()
        Counter = 0
        Increment = 100.0 / (len(tables) - 1)

        for table in tables:
            name = table[0]

            if name != 'version':
                Counter += 1
                Progress.update(int(Counter * Increment), message="Delete Texture Database: " + name)
                texdb.cursor.execute("DELETE FROM " + name)

        Progress.close()

    LOG.warning("[ reset artwork ]")

def get_credentials(Utils):
    path = Utils.translatePath("special://profile/addon_data/plugin.video.emby-next-gen/")

    if not xbmcvfs.exists(path):
        xbmcvfs.mkdirs(path)

    if xbmcvfs.exists(os.path.join(path, "data.json")):
        with open(os.path.join(path, 'data.json'), 'rb') as infile:
            credentials = json.load(infile)
    else:
        credentials = {}

    credentials['Servers'] = credentials.get('Servers', [])
    return credentials

def save_credentials(Utils, credentials):
    credentials = credentials or {}
    path = Utils.translatePath("special://profile/addon_data/plugin.video.emby-next-gen/")

    if not xbmcvfs.exists(path):
        xbmcvfs.mkdirs(path)

    credentials = json.dumps(credentials, sort_keys=True, indent=4, ensure_ascii=False)

    with open(os.path.join(path, 'data.json'), 'wb') as outfile:
        outfile.write(credentials.encode('utf-8'))

#Get Kodi ID from emby ID
def get_kodiID(Utils, emby_id):
    with Database(Utils, 'emby', True) as embydb:
        item = emby_db.EmbyDatabase(embydb.cursor).get_item_by_wild_id(emby_id)

        if not item:
            LOG.debug("Not an kodi item")
            return

    return item

#Get emby item based on kodi id and media
def get_item(Utils, kodi_id, media):
    with Database(Utils, 'emby', True) as embydb:
        item = emby_db.EmbyDatabase(embydb.cursor).get_full_item_by_kodi_id(kodi_id, media)

        if not item:
            LOG.debug("Not an emby item")
            return

    return item

def get_item_complete(Utils, kodi_id, media):
    with Database(Utils, 'emby', True) as embydb:
        item = emby_db.EmbyDatabase(embydb.cursor).get_full_item_by_kodi_id_complete(kodi_id, media)

        if not item:
            LOG.debug("Not an emby item")
            return

    return item

def get_Presentationkey(Utils, EmbyID):
    with Database(Utils, 'emby', True) as embydb:
        item = emby_db.EmbyDatabase(embydb.cursor).get_kodiid(EmbyID)

        if not item:
            LOG.debug("Not an emby item")
            return None

    return item[1]

#Get emby item based on kodi id and media
def get_ItemsByPresentationkey(Utils, PresentationKey):
    with Database(Utils, 'emby', True) as embydb:
        items = emby_db.EmbyDatabase(embydb.cursor).get_ItemsByPresentation_key(PresentationKey)

    return items

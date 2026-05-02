import os
import base64

try:
    import zipfile
    CompressionZip = True
except:
    CompressionZip = False

import xbmcvfs
import xbmc
from helper import utils

BackupInProgress = ""

# Create backup root folder
if not utils.backupPath:
    utils.set_settings("backupPath", "special://profile/addon_data/plugin.service.emby-next-gen/backup/")

if not xbmcvfs.exists(utils.backupPath):
    utils.mkDir(utils.backupPath)

def Backup():
    global BackupInProgress

    if not CompressionZip:
        utils.Dialog.notification(heading=utils.addon_name, message=utils.Translate(33756), icon=utils.icon, time=utils.displayMessage)
        return

    if BackupInProgress:
        utils.Dialog.notification(heading=utils.addon_name, message=f"{utils.Translate(33757)}: {BackupInProgress}", icon=utils.icon, time=utils.displayMessage)
        return

    xbmc.log("EMBY.helper.backup: -->[ backup ]", 1) # LOGINFO
    BackupFilename = utils.Dialog.input(heading=utils.Translate(33755), defaultt=f"Kodi{xbmc.getInfoLabel('System.BuildVersion')[:2]} - {xbmc.getInfoLabel('System.Date(yyyy-mm-dd)')} {xbmc.getInfoLabel('System.Time(hh:mm:ss xx)').replace(':', '-')}")

    if not BackupFilename:
        xbmc.log("EMBY.helper.backup: --<[ backup ] invalid file", 1) # LOGINFO
        return

    BackupInProgress = BackupFilename
    utils.close_dialog(10146) # addoninformation
    utils.create_ProgressBar("Backup", utils.Translate(33199), utils.Translate(33651))

    with zipfile.ZipFile(xbmcvfs.translatePath(f"{utils.backupPath}{BackupFilename}.zip"), 'w', zipfile.ZIP_STORED, strict_timestamps=False) as ZipFile: # Compression might corrupt data, do not use zipfile.ZIP_DEFLATED, user uncompressed!
        # Backup service plugin
        utils.update_ProgressBar("Backup", int(0 / 0.10), utils.Translate(33651), "plugin.service.emby-next-gen")
        compress_Folder("special://home/addons/plugin.service.emby-next-gen/", ZipFile, (), (), (".pyc",))

        # Backup audio plugin
        utils.update_ProgressBar("Backup", int(1 / 0.10), utils.Translate(33651), "plugin.audio.emby-next-gen")
        compress_Folder("special://home/addons/plugin.audio.emby-next-gen/", ZipFile, (), (), (".pyc",))

        # Backup video plugin
        utils.update_ProgressBar("Backup", int(2 / 0.10), utils.Translate(33651), "plugin.video.emby-next-gen")
        compress_Folder("special://home/addons/plugin.video.emby-next-gen/", ZipFile, (), (), (".pyc",))

        # Backup image plugin
        utils.update_ProgressBar("Backup", int(3 / 0.10), utils.Translate(33651), "plugin.image.emby-next-gen")
        compress_Folder("special://home/addons/plugin.image.emby-next-gen/", ZipFile, (), (), (".pyc",))

        # Backup userdata
        utils.update_ProgressBar("Backup", int(4 / 0.10), utils.Translate(33651), "userdata")
        compress_Folder(utils.FolderAddonUserdata, ZipFile, (utils.backupPath, os.path.join(utils.DownloadPath, "EMBY-offline-content", ''), utils.backupPath, os.path.join(utils.DownloadPath, "EMBY-themes", ''), "special://profile/addon_data/plugin.service.emby-next-gen/backup/"), (), ())

        # Backup library
        utils.update_ProgressBar("Backup", int(5 / 0.10), utils.Translate(33651), "library")
        compress_Folder("special://profile/library/", ZipFile, (), (), ())

        # Backup playlists
        utils.update_ProgressBar("Backup", int(6 / 0.10), utils.Translate(33651), "playlists")
        compress_Folder("special://profile/playlists/", ZipFile, (), (), ())

        # Backup music database
        utils.SyncPause["Backup"] = True
        utils.update_ProgressBar("Backup", int(7 / 0.10), utils.Translate(33651), "music database")
        busy_KodiDatabase()
        DatabaseSHM = f'{utils.DatabaseFiles["music"]}-shm'
        DatabaseWAL = f'{utils.DatabaseFiles["music"]}-wal'
        DatabaseCounter = 0

        while xbmcvfs.exists(DatabaseSHM) or xbmcvfs.exists(DatabaseWAL):
            xbmc.log(f"EMBY.helper.backup: music database is open, delay backup. Retry: {DatabaseCounter}", 1) # LOGINFO
            utils.sleep(1)
            DatabaseCounter += 1

            if DatabaseCounter > 60:
                xbmc.log(f"EMBY.helper.backup: music database is open, delay backup. Continue anyway (database open in read only leaves abandoned temp files), backup wal and shm files: {DatabaseCounter}", 1) # LOGINFO
                break

        compress_Folder("special://profile/Database/", ZipFile, (), ("MyMusic",), ())

        # Backup video database
        utils.update_ProgressBar("Backup", int(8 / 0.10), utils.Translate(33651), "video database")
        busy_KodiDatabase()
        DatabaseSHM = f'{utils.DatabaseFiles["video"]}-shm'
        DatabaseWAL = f'{utils.DatabaseFiles["video"]}-wal'
        DatabaseCounter = 0

        while xbmcvfs.exists(DatabaseSHM) or xbmcvfs.exists(DatabaseWAL):
            xbmc.log(f"EMBY.helper.backup: video database is open, delay backup. Retry: {DatabaseCounter}", 1) # LOGINFO
            utils.sleep(1)
            DatabaseCounter += 1

            if DatabaseCounter > 60:
                xbmc.log(f"EMBY.helper.backup: video database is open, delay backup. Continue anyway (database open in read only leaves abandoned temp files), backup wal and shm files: {DatabaseCounter}", 1) # LOGINFO
                break

        compress_Folder("special://profile/Database/", ZipFile, (), ("MyVideos",), ())

        # Backup emby database
        utils.update_ProgressBar("Backup", int(9 / 0.10), utils.Translate(33651), "emby database")

        for ServerId in utils.EmbyServers:
            EmbyDatabaseFile = utils.DatabaseFiles[ServerId]
            DatabaseSHM = f'{EmbyDatabaseFile}-shm'
            DatabaseWAL = f'{EmbyDatabaseFile}-wal'
            DatabaseCounter = 0

            while xbmcvfs.exists(DatabaseSHM) or xbmcvfs.exists(DatabaseWAL):
                xbmc.log(f"EMBY.helper.backup: emby database {ServerId} is open, delay backup. Retry: {DatabaseCounter}", 1) # LOGINFO
                utils.sleep(1)
                DatabaseCounter += 1

                if DatabaseCounter > 5:
                    xbmc.log(f"EMBY.helper.backup: video database {ServerId} is open, delay backup. Continue anyway (database open in read only leaves abandoned temp files), backup wal and shm files: {DatabaseCounter}", 1) # LOGINFO
                    break

        compress_Folder("special://profile/Database/", ZipFile, (), ("emby",), ())
        utils.SyncPause["Backup"] = False

        # Backup favourites
        utils.update_ProgressBar("Backup", int(10 / 0.10), utils.Translate(33651), "favourites")

        if xbmcvfs.exists("special://profile/favourites.xml"):
            compress_Files(["favourites.xml"], (), (), "special://profile/", ZipFile)

    utils.close_ProgressBar("Backup")
    utils.Dialog.notification(heading=utils.addon_name, message=f"{utils.Translate(33091)} {BackupFilename}", icon=utils.icon, time=utils.displayMessage)
    BackupInProgress = ""
    xbmc.log("EMBY.helper.backup: --<[ backup ]", 1) # LOGINFO

def Restore():
    if not CompressionZip:
        utils.Dialog.notification(heading=utils.addon_name, message=utils.Translate(33756), icon=utils.icon, time=utils.displayMessage)
        return

    if BackupInProgress:
        utils.Dialog.notification(heading=utils.addon_name, message=f"{utils.Translate(33757)}: {BackupInProgress}", icon=utils.icon, time=utils.displayMessage)
        return

    xbmc.log("EMBY.helper.backup: -->[ restore ]", 1) # LOGINFO
    utils.SystemShutdown = True
    RestoreFile = utils.Dialog.browseSingle(type=1, heading=utils.Translate(33643), shares='files', mask='.zip', defaultt=utils.backupPath)

    if not RestoreFile or not RestoreFile.lower().endswith(".zip"):
        xbmc.log(f"EMBY.helper.backup: --<[ restore ] invalid file: {RestoreFile}", 1) # LOGINFO
        return

    utils.close_dialog(10146) # addoninformation
    RestoreFile = xbmcvfs.translatePath(RestoreFile)
    FolderExtract = "special://profile/addon_data/plugin.service.emby-next-gen/extract/"
    utils.delFolder(FolderExtract)
    utils.mkDir(FolderExtract)
    FolderExtractReal = xbmcvfs.translatePath(FolderExtract)
    utils.create_ProgressBar("Restore", utils.Translate(33199), utils.Translate(33255))

    with zipfile.ZipFile(RestoreFile, 'r', strict_timestamps=False) as ZipFile:
        NameList = ZipFile.namelist()
        TotalItems = len(NameList) / 100

        for Index, CompressedFile in enumerate(NameList):
            utils.update_ProgressBar("Restore", Index / TotalItems, utils.Translate(33255), CompressedFile)

            ZipFile.extract(CompressedFile, path=FolderExtractReal)
            FileExtract = f"{FolderExtract}{CompressedFile}"
            FileDestination = f"special://{base64.urlsafe_b64decode(CompressedFile).decode('utf-8')}"

            if FileDestination.endswith(".db"):
                WALFile = FileDestination.replace(".db", ".db-wal")
                SHMFile = FileDestination.replace(".db", ".db-shm")

                if xbmcvfs.exists(WALFile):
                    utils.delFile(WALFile)

                if xbmcvfs.exists(SHMFile):
                    utils.delFile(SHMFile)

            if xbmcvfs.exists(FileDestination):
                utils.delFile(FileDestination)

            if not utils.renameFile(FileExtract, FileDestination):
                utils.copyFile(FileExtract, FileDestination)

    utils.delFolder(FolderExtract)
    utils.close_ProgressBar("Restore")
    utils.Dialog.notification(heading=utils.addon_name, message=f"{utils.Translate(33860)} {RestoreFile}", icon=utils.icon, time=utils.displayMessage)
    xbmc.log("EMBY.helper.backup: --<[ restore ]", 1) # LOGINFO
    utils.restart_kodi()

def Delete():
    xbmc.log("EMBY.helper.backup: -->[ delete ]", 1) # LOGINFO
    DeleteFile = utils.Dialog.browseSingle(type=1, heading=utils.Translate(33754), shares='files', mask='.zip', defaultt=utils.backupPath)

    if not DeleteFile:
        xbmc.log("EMBY.helper.backup: --<[ backup ] invalid file", 1) # LOGINFO
        return

    utils.delFile(DeleteFile)
    xbmc.log("EMBY.helper.backup: --<[ delete ]", 1) # LOGINFO

# Backup current plugin for rollbacks on updates
def create_Rollback():
    xbmc.log("EMBY.helper.backup: -->[ update rollback ]", 1) # LOGINFO
    Forced = False

    if utils.CurrentServicePluginVersion != utils.addon_version:
        Forced = True
        utils.set_settings("CurrentServicePluginVersion", utils.addon_version)

    # backup service plugin
    RollbackFolder = "special://profile/addon_data/plugin.service.emby-next-gen/rollback/plugin.service.emby-next-gen/"
    Exists = xbmcvfs.exists(RollbackFolder)

    if Exists and Forced:
        xbmc.log("EMBY.helper.backup: update rollback: delete plugin.service.emby-next-gen", 1) # LOGINFO
        utils.delFolder(RollbackFolder)
        Exists = False

    if not Exists:
        xbmc.log("EMBY.helper.backup: copy rollback: delete plugin.service.emby-next-gen", 1) # LOGINFO
        utils.mkDir("special://profile/addon_data/plugin.service.emby-next-gen/rollback/")
        utils.mkDir(RollbackFolder)
        utils.copytree("special://home/addons/plugin.service.emby-next-gen/", RollbackFolder, (".pyc",), True, False)

    # backup audio plugin
    RollbackFolder = "special://profile/addon_data/plugin.service.emby-next-gen/rollback/plugin.audio.emby-next-gen/"
    Exists = xbmcvfs.exists(RollbackFolder)

    if Exists and Forced:
        xbmc.log("EMBY.helper.backup: update rollback: delete plugin.audio.emby-next-gen", 1) # LOGINFO
        utils.delFolder(RollbackFolder)
        Exists = False

    if not Exists and xbmcvfs.exists("special://home/addons/plugin.audio.emby-next-gen/"):
        xbmc.log("EMBY.helper.backup: copy rollback: delete plugin.audio.emby-next-gen", 1) # LOGINFO
        utils.mkDir("special://profile/addon_data/plugin.service.emby-next-gen/rollback/")
        utils.mkDir(RollbackFolder)
        utils.copytree("special://home/addons/plugin.audio.emby-next-gen/", RollbackFolder, (".pyc",), True, False)

    # backup video plugin
    RollbackFolder = "special://profile/addon_data/plugin.service.emby-next-gen/rollback/plugin.video.emby-next-gen/"
    Exists = xbmcvfs.exists(RollbackFolder)

    if Exists and Forced:
        xbmc.log("EMBY.helper.backup: update rollback: delete plugin.video.emby-next-gen", 1) # LOGINFO
        utils.delFolder(RollbackFolder)
        Exists = False

    if not Exists and xbmcvfs.exists("special://home/addons/plugin.video.emby-next-gen/"):
        xbmc.log("EMBY.helper.backup: copy rollback: delete plugin.video.emby-next-gen", 1) # LOGINFO
        utils.mkDir("special://profile/addon_data/plugin.service.emby-next-gen/rollback/")
        utils.mkDir(RollbackFolder)
        utils.copytree("special://home/addons/plugin.video.emby-next-gen/", RollbackFolder, (".pyc",), True, False)

    # backup image plugin
    RollbackFolder = "special://profile/addon_data/plugin.service.emby-next-gen/rollback/plugin.image.emby-next-gen/"
    Exists = xbmcvfs.exists(RollbackFolder)

    if Exists and Forced:
        xbmc.log("EMBY.helper.backup: update rollback: delete plugin.image.emby-next-gen", 1) # LOGINFO
        utils.delFolder(RollbackFolder)
        Exists = False

    if not Exists and xbmcvfs.exists("special://home/addons/plugin.image.emby-next-gen/"):
        xbmc.log("EMBY.helper.backup: copy rollback: delete plugin.image.emby-next-gen", 1) # LOGINFO
        utils.mkDir("special://profile/addon_data/plugin.service.emby-next-gen/rollback/")
        utils.mkDir(RollbackFolder)
        utils.copytree("special://home/addons/plugin.image.emby-next-gen/", RollbackFolder, (".pyc",), True, False)

    xbmc.log("EMBY.helper.backup: --<[ update rollback ]", 1) # LOGINFO

def restore_Rollback():
    Success = False
    xbmc.log("EMBY.helper.backup: -->[ rollback ]", 1) # LOGINFO
    # Restore service plugin
    RestoreServicePlugin = "special://profile/addon_data/plugin.service.emby-next-gen/rollback/plugin.service.emby-next-gen/"

    if xbmcvfs.exists(RestoreServicePlugin):
        utils.copytree(RestoreServicePlugin, "special://home/addons/plugin.service.emby-next-gen/", (), True, True)
        Success = True

    # Restore video plugin
    RestoreVideoPlugin = "special://profile/addon_data/plugin.service.emby-next-gen/rollback/plugin.video.emby-next-gen/"

    if xbmcvfs.exists(RestoreVideoPlugin):
        utils.copytree(RestoreVideoPlugin, "special://home/addons/plugin.video.emby-next-gen/", (), True, True)

    # Restore audio plugin
    RestoreAudioPlugin = "special://profile/addon_data/plugin.service.emby-next-gen/rollback/plugin.audio.emby-next-gen/"

    if xbmcvfs.exists(RestoreAudioPlugin):
        utils.copytree(RestoreAudioPlugin, "special://home/addons/plugin.audio.emby-next-gen/", (), True, True)

    # Restore image plugin
    RestoreImagePlugin = "special://profile/addon_data/plugin.service.emby-next-gen/rollback/plugin.image.emby-next-gen/"

    if xbmcvfs.exists(RestoreImagePlugin):
        utils.copytree(RestoreImagePlugin, "special://home/addons/plugin.image.emby-next-gen/", (), True, True)

    xbmc.log("EMBY.helper.backup: --<[ rollback ]", 1) # LOGINFO
    return Success

def compress_Folder(PathSource, ZipFile, FoldersExclude, FileBegins, FileEndsExclude):
    Folders, Filenames = xbmcvfs.listdir(PathSource)

    if Folders:
        compress_Recursive(PathSource, Folders, FoldersExclude, FileBegins, FileEndsExclude, ZipFile)

    compress_Files(Filenames, FileBegins, FileEndsExclude, PathSource, ZipFile)
    xbmc.log(f"EMBY.helper.utils: Compressed {PathSource}", 1) # LOGINFO

def compress_Recursive(PathSource, Folders, FoldersExclude, FileBegins, FileEndsExclude, ZipFile):
    for Folder in Folders:
        FolderSource = os.path.join(PathSource, Folder, '')

        # Skip folder by FoldersExclude
        if FolderSource in FoldersExclude:
            if utils.DebugLog: xbmc.log(f"EMBY.helper.utils (DEBUG): Skip folder compress {FolderSource}", 1) # LOGDEBUG
            continue

        SubFolders, Filenames = xbmcvfs.listdir(FolderSource)

        if SubFolders:
            compress_Recursive(FolderSource, SubFolders, FoldersExclude, FileBegins, FileEndsExclude, ZipFile)

        compress_Files(Filenames, FileBegins, FileEndsExclude, FolderSource, ZipFile)

def compress_Files(Filenames, FileBegins, FileEndsExclude, FolderSource, ZipFile):
    for Filename in Filenames:
        # Filter by filename begin
        if FileBegins:
            for FileBegin in FileBegins:
                if Filename.startswith(FileBegin):
                    break
            else: # prefix not found
                if utils.DebugLog: xbmc.log(f"EMBY.helper.utils (DEBUG): Filecompress filtered by filename begin: {Filename}", 1) # LOGDEBUG
                continue

        # Filter by exclude filename end
        if FileEndsExclude:
            Skip = False

            for FileEndExclude in FileEndsExclude:
                if Filename.endswith(FileEndExclude):
                    Skip = True
                    break

            if Skip:
                if utils.DebugLog: xbmc.log(f"EMBY.helper.utils (DEBUG): Filecompress filtered by excluded filename end: {Filename}", 1) # LOGDEBUG
                continue

        CompressFile = xbmcvfs.translatePath(os.path.join(FolderSource, Filename))

        if xbmcvfs.exists(CompressFile):
            ArchiveName = base64.urlsafe_b64encode(f"{FolderSource.replace('special://', '')}{Filename}".encode('utf-8')).decode('utf-8') # workaround for zipfile ascii issues
            ZipFile.write(CompressFile.encode('utf-8'), arcname=ArchiveName)
        else:
            if utils.DebugLog: xbmc.log(f"EMBY.helper.utils (DEBUG): Filecompress, file not found: {CompressFile}", 1) # LOGDEBUG

def busy_KodiDatabase():
    xbmc.log("EMBY.helper.backup (DEBUG): CONDITION: --->[ SyncPauseCondition ]", 1) # LOGDEBUG

    with utils.SafeLock(utils.SyncPauseCondition):
        while 'kodi_rw' in utils.SyncPause and utils.SyncPause['kodi_rw']:
            utils.SyncPauseCondition.wait(timeout=0.1)

    xbmc.log("EMBY.helper.backup (DEBUG): CONDITION: ---<[ SyncPauseCondition ]", 1) # LOGDEBUG
    xbmc.log("EMBY.helper.backup: Kodi database is busy, delay backup.", 1) # LOGINFO

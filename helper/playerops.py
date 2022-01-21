# -*- coding: utf-8 -*-
import json
import xbmc
from helper import utils
from database import dbio
from emby import listitem

XbmcMonitor = xbmc.Monitor()


def AddPlaylistItem(Position, EmbyID, Offset, EmbyServer):
    embydb = dbio.DBOpen(EmbyServer.server_id)
    Data = embydb.get_item_by_wild_id(str(EmbyID))
    dbio.DBClose(EmbyServer.server_id, False)

    if Data:  # Requested video is synced to KodiDB. No additional info required
        if Data[0][1] in ("song", "album", "artist"):
            playlistID = 0
            playlist = xbmc.PlayList(xbmc.PLAYLIST_MUSIC)
        else:
            playlistID = 1
            playlist = xbmc.PlayList(xbmc.PLAYLIST_VIDEO)

        Pos = GetPlaylistPos(Position, playlist, Offset)
        params = {'playlistid': playlistID, 'position': Pos, 'item': {'%sid' % Data[0][1]: int(Data[0][0])}}
        xbmc.executeJSONRPC(json.dumps({'jsonrpc': "2.0", 'id': 1, 'method': 'Playlist.Insert', 'params': params}))
    else:
        item = EmbyServer.API.get_item(EmbyID)
        li = listitem.set_ListItem(item, EmbyServer.server_id)
        path, Type = utils.get_path_type_from_item(EmbyServer.server_id, item)

        if not path:
            return False, False, None

        if Type == "picture":
            return True, False, path

        li.setProperty('path', path)

        if Type == "audio":
            playlist = xbmc.PlayList(xbmc.PLAYLIST_MUSIC)
        else:
            playlist = xbmc.PlayList(xbmc.PLAYLIST_VIDEO)

        Pos = GetPlaylistPos(Position, playlist, Offset)
        playlist.add(path, li, index=Pos)

    return True, True, playlist

# Websocket command from Emby server
def Play(ItemIds, PlayCommand, StartIndex, StartPositionTicks, EmbyServer):
    FirstItem = True
    Offset = 0

    for ID in ItemIds:
        playlist = None
        Offset += 1
        Found = False
        isPlaylist = False

        if PlayCommand == "PlayNow":
            Found, isPlaylist, playlist = AddPlaylistItem("current", ID, Offset, EmbyServer)
        elif PlayCommand == "PlayNext":
            Found, isPlaylist, playlist = AddPlaylistItem("current", ID, Offset, EmbyServer)
        elif PlayCommand == "PlayLast":
            Found, isPlaylist, playlist = AddPlaylistItem("last", ID, 0, EmbyServer)

        if not Found:
            continue

        if not isPlaylist:  # picture
            xbmc.executebuiltin(playlist)
            return

        # Play Item
        if PlayCommand == "PlayNow":
            if StartIndex != -1:
                if Offset == int(StartIndex + 1):
                    if FirstItem:
                        Pos = playlist.getposition()

                        if Pos == -1:
                            Pos = 0

                        PlaylistStartIndex = Pos + Offset
                        xbmc.Player().play(item=playlist, startpos=PlaylistStartIndex)
                        setPlayerPosition(StartPositionTicks)
                        Offset = 0
                        FirstItem = False
            else:
                if FirstItem:
                    Pos = playlist.getposition()

                    if Pos == -1:
                        Pos = 0

                    xbmc.Player().play(item=playlist, startpos=Pos + Offset)
                    setPlayerPosition(StartPositionTicks)
                    Offset = 0
                    FirstItem = False

def setPlayerPosition(StartPositionTicks):
    if StartPositionTicks != -1:
        Position = StartPositionTicks / 10000000

        for _ in range(10):
            if xbmc.Player().isPlaying():
                for _ in range(10):
                    xbmc.Player().seekTime(Position)
                    CurrentTime = xbmc.Player().getTime()

                    if CurrentTime >= Position - 10:
                        return

                    if XbmcMonitor.waitForAbort(0.5):
                        return
            else:
                if XbmcMonitor.waitForAbort(0.5):
                    return

def GetPlaylistPos(Position, playlist, Offset):
    if Position == "current":
        Pos = playlist.getposition()

        if Pos == -1:
            Pos = 0

        Pos = Pos + Offset
    elif Position == "previous":
        Pos = playlist.getposition()

        if Pos == -1:
            Pos = 0
    elif Position == "last":
        Pos = playlist.size()
    else:
        Pos = Position

    return Pos

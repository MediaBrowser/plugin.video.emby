import importlib.util
import json
from pathlib import Path
import sys
import threading
import types
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]


class FakeQueue:
    def __init__(self):
        self.items = []

    def get(self):
        return self.items.pop(0)

    def getall(self):
        items = self.items[:]
        self.items.clear()
        return items

    def put(self, item):
        self.items.append(item)


class FakePlaylist:
    def __init__(self):
        self.items = []
        self.position = -1

    def add(self, path, listitem=None, index=None):
        if index is None:
            self.items.append(path)
        else:
            self.items.insert(index, path)

    def clear(self):
        self.items.clear()

    def getposition(self):
        return self.position

    def size(self):
        return len(self.items)


class FakeClient:
    def __init__(self, request, on_close):
        self.request = request.encode("utf-8")
        self.on_close = on_close
        self.sent = []

    def settimeout(self, timeout):
        pass

    def recv(self, size):
        return self.request

    def send(self, data):
        self.sent.append(data)

    def close(self):
        self.on_close()


class PlaybackHarness:
    def __init__(self):
        self.playlists = [FakePlaylist(), FakePlaylist()]
        self.json_calls = []
        self.server = mock.Mock()
        self.server.ServerData = {"ServerId": "server-1"}
        self.server.EmbySession = []
        self.server.API = mock.Mock()
        self.db = mock.Mock()
        self.db.get_KodiId_by_EmbyId.return_value = (202, "episode")
        self.saved_modules = {}
        self.saved_attributes = []
        self._install()

    def _module(self, name, **attributes):
        module = types.ModuleType(name)
        for key, value in attributes.items():
            setattr(module, key, value)
        return module

    def _replace_module(self, name, module):
        self.saved_modules[name] = sys.modules.get(name)
        sys.modules[name] = module

    def _set_attribute(self, parent, name, value):
        existed = hasattr(parent, name)
        previous = getattr(parent, name, None)
        self.saved_attributes.append((parent, name, existed, previous))
        setattr(parent, name, value)

    def _load(self, name, relative_path):
        spec = importlib.util.spec_from_file_location(name, ROOT / relative_path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
        return module

    def _send_json(self, payload, get_result=False):
        data = json.loads(payload)
        self.json_calls.append(data)
        method = data.get("method")
        params = data.get("params", {})

        if method == "Playlist.Insert":
            item = params["item"]
            media_type = next(iter(item))
            self.playlists[params["playlistid"]].items.insert(
                params["position"], f"{media_type}:{item[media_type]}"
            )
        elif method == "Playlist.Remove":
            self.playlists[params["playlistid"]].items.pop(params["position"])

        return {"result": {}}

    def _install(self):
        import core
        import database
        import dialogs
        import emby
        import helper
        import hooks

        xbmc = self._module(
            "xbmc",
            Player=lambda: mock.Mock(),
            PlayList=lambda playlist_id: self.playlists[playlist_id],
            Keyboard=lambda: mock.Mock(),
            log=mock.Mock(),
            executebuiltin=mock.Mock(),
        )
        xbmcgui = self._module("xbmcgui", getCurrentWindowId=lambda: 12005)
        queue = self._module("helper.queue", Queue=FakeQueue)
        cache = self._module(
            "helper.cache",
            QueryCache={},
            update_querycache_userdata=mock.Mock(),
        )
        utils = self._module(
            "helper.utils",
            DebugLog=False,
            WebserviceWorkers=1,
            SystemShutdown=False,
            remotecontrol_client_control=False,
            RemoteMode=False,
            KodiTypeMapping={"episode": "episode"},
            Playlists=self.playlists,
            EmbyServers={"server-1": self.server},
            SendJson=self._send_json,
            SafeLock=lambda lock: lock,
            ActivateWindow=mock.Mock(),
            readFileBinary=lambda path: b"",
            start_thread=mock.Mock(),
            update_SyncPause=mock.Mock(),
            unset_SyncLock=mock.Mock(),
            closeall_ProgressBar=mock.Mock(),
            currenttime=lambda: "now",
            ItemSkipUpdate=[],
            PauseSyncDuringPlayback=False,
            PauseSyncDuringPlaybackStateChange=False,
            skipintroembuarydesign=False,
            CustomDialogParameters=(),
        )
        dbio = self._module(
            "database.dbio",
            DBOpenRO=lambda server_id, task: self.db,
            DBCloseRO=mock.Mock(),
        )
        listitem = self._module("emby.listitem")
        common = self._module("core.common")
        skipintrocredits = self._module(
            "dialogs.skipintrocredits",
            SkipIntro=lambda *args: mock.Mock(dialog_open=False),
        )

        modules = {
            "xbmc": xbmc,
            "xbmcgui": xbmcgui,
            "helper.utils": utils,
            "helper.queue": queue,
            "helper.cache": cache,
            "database.dbio": dbio,
            "emby.listitem": listitem,
            "core.common": common,
            "dialogs.skipintrocredits": skipintrocredits,
        }
        for name, module in modules.items():
            self._replace_module(name, module)

        for parent, name, module in (
            (helper, "utils", utils),
            (helper, "queue", queue),
            (helper, "cache", cache),
            (database, "dbio", dbio),
            (emby, "listitem", listitem),
            (core, "common", common),
            (dialogs, "skipintrocredits", skipintrocredits),
        ):
            self._set_attribute(parent, name, module)

        self.playerops = self._load("helper.playerops", "helper/playerops.py")
        self._set_attribute(helper, "playerops", self.playerops)

        upnext = self._module("helper.upnext", dispatch=mock.Mock())
        self._replace_module("helper.upnext", upnext)
        self._set_attribute(helper, "upnext", upnext)
        self.player = self._load("helper.player", "helper/player.py")
        self._set_attribute(helper, "player", self.player)

        metadata = self._module("emby.metadata")
        httpcache = self._module("emby.httpcache")
        favorites = self._module("hooks.favorites")
        context = self._module("helper.context")
        pluginmenu = self._module("helper.pluginmenu")
        xmls = self._module(
            "helper.xmls", load_defaultvideosettings=lambda: {}
        )
        for name, module in (
            ("emby.metadata", metadata),
            ("emby.httpcache", httpcache),
            ("hooks.favorites", favorites),
            ("helper.context", context),
            ("helper.pluginmenu", pluginmenu),
            ("helper.xmls", xmls),
        ):
            self._replace_module(name, module)

        for parent, name, module in (
            (emby, "metadata", metadata),
            (emby, "httpcache", httpcache),
            (hooks, "favorites", favorites),
            (helper, "context", context),
            (helper, "pluginmenu", pluginmenu),
            (helper, "xmls", xmls),
        ):
            self._set_attribute(parent, name, module)

        self.webservice = self._load("hooks.webservice", "hooks/webservice.py")
        self._set_attribute(hooks, "webservice", self.webservice)

    def close(self):
        for parent, name, existed, previous in reversed(self.saved_attributes):
            if existed:
                setattr(parent, name, previous)
            else:
                delattr(parent, name)

        for name, previous in self.saved_modules.items():
            if previous is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = previous

    def handoff(self, item_id="2"):
        request = (
            "EVENT service;1;?mode=play&server=server-1&item=" + item_id
        )
        client = FakeClient(
            request,
            lambda: setattr(self.webservice, "Running", False),
        )
        self.webservice.WorkerQueue.items = [client]
        self.webservice.Running = True
        self.webservice.worker_Query(0)
        return client


class UpNextPlaybackIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.harness = PlaybackHarness()
        self.addCleanup(self.harness.close)
        self.play_url = (
            "plugin://plugin.service.emby-next-gen/"
            "?mode=play&server=server-1&item=2"
        )

    def test_automatic_advance_replaces_queued_url_without_losing_playlist_tail(self):
        playlist = self.harness.playlists[1]
        playlist.items = ["current", self.play_url, "remaining-a", "remaining-b"]
        playlist.position = 1

        client = self.harness.handoff()

        self.assertEqual(client.sent, [self.harness.webservice.sendOK])
        if self.harness.player.PlaylistRemoveItem != -1:
            self.harness.playerops.RemovePlaylistItem(
                1, self.harness.player.PlaylistRemoveItem
            )
            self.harness.player.PlaylistRemoveItem = -1
        self.assertEqual(
            playlist.items,
            ["current", "episodeid:202", "remaining-a", "remaining-b"],
        )
        self.assertEqual(playlist.items.count("episodeid:202"), 1)

    def test_watch_now_ignores_delayed_stop_from_prior_episode(self):
        playlist = self.harness.playlists[1]
        playlist.items = ["current", self.play_url, "remaining"]
        playlist.position = 1
        self.harness.handoff()
        self.harness.playerops.RemovePlaylistItem(
            1, self.harness.player.PlaylistRemoveItem
        )
        self.harness.player.PlaylistRemoveItem = -1

        session = {
            "ItemId": 2,
            "PositionTicks": 0,
            "RunTimeTicks": 1_800 * 10_000_000,
        }
        self.harness.player.PlayingItem = [
            session,
            0,
            0,
            0,
            self.harness.server,
            1,
            "episode",
            "",
        ]
        self.harness.player.EmbyPlaying = True
        self.harness.player.PlayItem = (202, "episode")
        self.harness.player.PlayerEventsQueue.items = [
            (
                "stop",
                json.dumps(
                    {
                        "end": True,
                        "item": {"id": 101, "type": "episode"},
                    }
                ),
            ),
            "QUIT",
        ]

        self.harness.player.PlayerCommands()

        self.harness.server.API.session_stop.assert_not_called()
        self.assertEqual(self.harness.player.PlayingItem[0]["ItemId"], 2)
        self.assertEqual(self.harness.player.PlayItem, (202, "episode"))
        self.assertEqual(
            playlist.items,
            ["current", "episodeid:202", "remaining"],
        )


if __name__ == "__main__":
    unittest.main()

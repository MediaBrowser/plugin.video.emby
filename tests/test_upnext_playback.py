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


class TrackingServers(dict):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.lookups = []

    def __getitem__(self, key):
        self.lookups.append(key)
        return super().get(key, next(iter(self.values())))


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
        self.server.ServerData = {
            "ServerId": "server-1",
            "ServerUrl": "https://emby.example",
            "AccessToken": "secret-token",
        }
        self.server.EmbySession = []
        self.server.API = mock.Mock()
        self.servers = TrackingServers({"server-1": self.server})
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
            EmbyServers=self.servers,
            SendJson=self._send_json,
            SafeLock=lambda lock: lock,
            EmbyServerOnlineCondition=threading.Condition(),
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
            nodesreset=mock.Mock(),
            enableCoverArt=False,
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

        def load_metadata(payload, is_picture, is_audio):
            path_parts = payload.split("/")
            image_parts = path_parts[-1].split("-")
            image_types = {
                "p": "Primary",
                "a": "Art",
                "l": "Logo",
                "t": "Thumb",
                "B": "Backdrop",
            }
            return {
                "MediaSources": [],
                "Payload": payload,
                "Type": "picture",
                "ServerId": path_parts[2],
                "EmbyId": image_parts[1],
                "MediaType": "p",
                "ImageIndex": image_parts[2],
                "ImageType": image_types[image_parts[3]],
                "ImageTag": image_parts[4],
                "Overlay": "",
                "DelayedContentSet": False,
                "SelectionIndexMediaSource": 0,
                "SelectionIndexVideoStream": 0,
                "SelectionIndexAudioStream": 0,
                "SelectionIndexSubtitleStream": -1,
                "isDynamic": False,
                "isHttp": False,
            }

        metadata = self._module("emby.metadata", load_MetaData=load_metadata)
        httpcache = self._module("emby.httpcache", get=lambda payload: None)
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
        self.utils = utils
        self.pluginmenu = pluginmenu

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

    def handoff_query(self, query):
        request = "EVENT service;1;?" + query
        client = FakeClient(
            request,
            lambda: setattr(self.webservice, "Running", False),
        )
        self.webservice.WorkerQueue.items = [client]
        self.webservice.Running = True
        self.webservice.worker_Query(0)
        return client

    def handoff(self, item_id="2"):
        return self.handoff_query(f"mode=play&server=server-1&item={item_id}")

    def picture(self, path):
        client = FakeClient(
            f"GET {path} HTTP/1.1",
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

    def test_rejects_invalid_play_queries_before_sensitive_sinks(self):
        invalid_queries = (
            "mode=play&mode=nodesreset&server=server-1&item=2",
            "mode=nodesreset&mode=play&server=server-1&item=2",
            "mode=play&server=server-1&server=other&item=2",
            "mode=play&server=server-1&item=2&item=3",
            "mode=play&item=2",
            "mode=play&server=server-1",
            "mode=play&server=server-1&item=2&unexpected=value",
            "mode=play&server=server-1&item=2%26mode%3Dnodesreset",
            "mode=play&server=server-1&item=2%3Dnodesreset",
            "mode=play&server=server-1&item=2%25nodesreset",
            "mode=play&server=server-1&item=2%3Fnodesreset",
            "mode=play&server=server-1&item=2%2Fnodesreset",
            "mode=play&server=server-1&item=2%5Cnodesreset",
            "mode=play&server=server-1&item=2%0D%0Anodesreset",
            "mode=play&server=server%26mode%3Dnodesreset&item=2",
            "mode=play&server=server%3Dnodesreset&item=2",
            "mode=play&server=server%25nodesreset&item=2",
            "mode=play&server=server%3Fnodesreset&item=2",
            "mode=play&server=server%2Fnodesreset&item=2",
            "mode=play&server=server%5Cnodesreset&item=2",
            "mode=play&server=server%0D%0Anodesreset&item=2",
        )

        for query in invalid_queries:
            with self.subTest(query=query):
                self.harness.servers.lookups.clear()
                self.harness.db.reset_mock()
                self.harness.utils.nodesreset.reset_mock()
                self.harness.pluginmenu.databasereset = mock.Mock()
                self.harness.player.PlaylistRemoveItem = 47

                with mock.patch.object(
                    self.harness.playerops, "GetPlaylistPosition"
                ) as get_position, mock.patch.object(
                    self.harness.playerops, "PlayEmby"
                ) as play_emby:
                    client = self.harness.handoff_query(query)

                self.assertEqual(client.sent, [self.harness.webservice.sendNotFound])
                self.assertEqual(self.harness.servers.lookups, [])
                self.assertEqual(self.harness.player.PlaylistRemoveItem, 47)
                get_position.assert_not_called()
                play_emby.assert_not_called()
                self.harness.db.get_KodiId_by_EmbyId.assert_not_called()
                self.harness.utils.nodesreset.assert_not_called()
                self.harness.pluginmenu.databasereset.assert_not_called()

    def test_numeric_item_plays_with_guid_and_established_server_ids(self):
        server_ids = (
            "2a38697ffc1b428b943aa1b6014e2263",
            "2a38697f-fc1b-428b-943a-a1b6014e2263",
        )

        for server_id in server_ids:
            with self.subTest(server_id=server_id):
                self.harness.servers[server_id] = self.harness.server
                self.harness.server.ServerData["ServerId"] = server_id
                self.harness.playlists[1].position = 0

                client = self.harness.handoff_query(
                    f"mode=play&server={server_id}&item=58574"
                )

                self.assertEqual(client.sent, [self.harness.webservice.sendOK])
                self.assertEqual(
                    self.harness.db.get_KodiId_by_EmbyId.call_args.args,
                    ("58574",),
                )
                self.harness.db.reset_mock()

    def test_upnext_artwork_is_returned_locally_without_credentials(self):
        artwork = (
            ("/picture/server-1/p-10-0-p-aabbcc01", "10", "Primary"),
            ("/picture/server-1/p-58574-0-l-aabbcc02", "58574", "Logo"),
            ("/picture/server-1/p-58574-0-B-aabbcc03", "58574", "Backdrop"),
            ("/picture/server-1/p-58574-0-t-aabbcc04", "58574", "Thumb"),
            ("/picture/server-1/p-58574-0-p-aabbcc05", "58574", "Primary"),
        )
        self.harness.server.API.get_Image_Binary.return_value = (
            b"image-data",
            "image/png",
            "png",
        )

        for path, item_id, image_type in artwork:
            with self.subTest(path=path):
                self.harness.server.API.get_Image_Binary.reset_mock()

                client = self.harness.picture(path)

                self.assertEqual(len(client.sent), 1)
                response = client.sent[0]
                headers, body = response.split(b"\r\n\r\n", 1)
                self.assertTrue(headers.startswith(b"HTTP/1.1 200 OK\r\n"))
                self.assertIn(b"Content-Type: image/png", headers)
                self.assertNotIn(b"Location:", headers)
                self.assertEqual(body, b"image-data")
                self.harness.server.API.get_Image_Binary.assert_called_once_with(
                    item_id,
                    image_type,
                    "0",
                    path.rsplit("-", 1)[-1],
                    False,
                )
                self.assert_credential_free(response)

    def test_picture_failures_are_credential_free_not_found_responses(self):
        path = "/picture/server-1/p-10-0-p-aabbcc01"
        failures = (
            ("empty image", (b"", "image/png", "png")),
            ("fetch exception", RuntimeError("secret-token https://emby.example")),
        )

        for label, result in failures:
            with self.subTest(failure=label):
                if isinstance(result, Exception):
                    self.harness.server.API.get_Image_Binary.side_effect = result
                else:
                    self.harness.server.API.get_Image_Binary.side_effect = None
                    self.harness.server.API.get_Image_Binary.return_value = result

                client = self.harness.picture(path)

                self.assertEqual(client.sent, [self.harness.webservice.sendNotFound])
                self.assert_credential_free(client.sent[0])

        self.harness.server.API.get_Image_Binary.side_effect = None
        with mock.patch.object(
            self.harness.webservice, "wait_for_Embyserver", return_value=True
        ) as wait_for_server:
            missing = self.harness.picture(
                "/picture/missing-server/p-10-0-p-aabbcc01"
            )
        self.assertEqual(missing.sent, [self.harness.webservice.sendNotFound])
        self.assert_credential_free(missing.sent[0])
        wait_for_server.assert_not_called()

    def assert_credential_free(self, response):
        for secret in (
            b"secret-token",
            b"https://emby.example",
            b"api_key",
            b"AccessToken",
            b"ServerUrl",
        ):
            self.assertNotIn(secret, response)

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

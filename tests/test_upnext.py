import base64
import importlib
import json
import sys
import types
import unittest
from unittest import mock


xbmc = types.ModuleType("xbmc")
xbmc.executeJSONRPC = mock.Mock(return_value='{"jsonrpc":"2.0","id":1,"result":"OK"}')
xbmc.getCondVisibility = mock.Mock(return_value=False)
xbmc.log = mock.Mock()
sys.modules["xbmc"] = xbmc

utils = types.ModuleType("helper.utils")
utils.start_thread = mock.Mock()
sys.modules["helper.utils"] = utils

upnext = importlib.import_module("helper.upnext")


def episode(item_id, season, number, **extra):
    item = {
        "Id": str(item_id),
        "Type": "Episode",
        "SeriesId": "series-1",
        "SeriesName": "Example Show",
        "Name": f"Episode {number}",
        "ParentIndexNumber": season,
        "IndexNumber": number,
        "RunTimeTicks": 1_800 * 10_000_000,
    }
    item.update(extra)
    return item


class FakeAPI:
    def __init__(self, current, episodes):
        self.current = current
        self.episodes = episodes
        self.get_item_calls = []
        self.get_items_calls = []
        self.get_episodes_calls = []

    def get_Item(self, *args):
        self.get_item_calls.append(args)
        return self.current

    def get_Items(self, *args):
        self.get_items_calls.append(args)
        return iter(self.episodes)

    def get_Episodes(self, *args):
        self.get_episodes_calls.append(args)
        return self.episodes


class FakeServer:
    def __init__(self, current, episodes):
        self.API = FakeAPI(current, episodes)
        self.ServerData = {
            "ServerId": "server-1",
            "ServerUrl": "https://emby.example",
            "AccessToken": "secret-token",
            "DeviceId": "secret-device",
        }


class EpisodeEndpointTests(unittest.TestCase):
    def test_requests_server_episode_order_adjacent_to_current_episode(self):
        dbio = types.ModuleType("database.dbio")
        listitem = types.ModuleType("emby.listitem")
        httpcache = types.ModuleType("emby.httpcache")

        with mock.patch.dict(
            sys.modules,
            {
                "database.dbio": dbio,
                "emby.listitem": listitem,
                "emby.httpcache": httpcache,
            },
        ):
            api_module = importlib.import_module("emby.api")

        server = mock.Mock()
        server.ServerData = {"UserId": "user-1"}
        server.http.request.return_value = (
            200,
            {},
            {"Items": [episode(10, 1, 1), episode(15, 0, 0)]},
        )
        api = object.__new__(api_module.API)
        api.EmbyServer = server
        api.DynamicListsRemoveFields = ()

        result = api.get_Episodes("series-1", "10")

        self.assertEqual([item["Id"] for item in result], ["10", "15"])
        request = server.http.request.call_args.args
        self.assertEqual(request[0:2], ("GET", "Shows/series-1/Episodes"))
        self.assertEqual(request[2]["AdjacentTo"], "10")
        self.assertEqual(request[2]["UserId"], "user-1")
        self.assertTrue(request[2]["EnableImages"])
        self.assertTrue(request[2]["EnableUserData"])
        self.assertNotIn("SortBy", request[2])
        self.assertNotIn("SortOrder", request[2])


class UpNextSignalTests(unittest.TestCase):
    def setUp(self):
        xbmc.executeJSONRPC.reset_mock()
        xbmc.getCondVisibility.reset_mock()
        xbmc.getCondVisibility.return_value = True
        xbmc.log.reset_mock()
        utils.start_thread.reset_mock()

    def decoded_signal(self):
        xbmc.executeJSONRPC.assert_called_once()
        envelope = json.loads(xbmc.executeJSONRPC.call_args.args[0])
        self.assertEqual(len(envelope["params"]["data"]), 1)
        encoded_payload = envelope["params"]["data"][0]
        payload = json.loads(base64.b64decode(encoded_payload).decode("utf-8"))
        return envelope, payload

    def test_sends_exact_signal_envelope_metadata_art_and_safe_play_url(self):
        current = episode(
            10,
            1,
            1,
            Name="Pilot",
            Overview="Current plot",
            CommunityRating="8.5",
            PremiereDate="2025-01-01",
            UserData={"PlayCount": 2},
            ImageTags={"Primary": "episode-current"},
            SeriesPrimaryImageTag="series-poster",
            ParentLogoItemId="series-1",
            ParentLogoImageTag="series-logo",
            ParentBackdropItemId="series-1",
            ParentBackdropImageTags=["series-fanart"],
            ParentThumbItemId="series-1",
            ParentThumbImageTag="series-landscape",
        )
        following = episode(11, 1, 2, Name="Second")
        server = FakeServer(current, [current, following])

        self.assertTrue(upnext.send_upnext(server, "10", 1_800 * 10_000_000, 0))

        envelope, payload = self.decoded_signal()
        self.assertEqual(
            envelope,
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "JSONRPC.NotifyAll",
                "params": {
                    "sender": "plugin.service.emby-next-gen.SIGNAL",
                    "message": "upnext_data",
                    "data": envelope["params"]["data"],
                },
            },
        )
        self.assertEqual(
            payload["current_episode"],
            {
                "episodeid": "10",
                "tvshowid": "series-1",
                "title": "Pilot",
                "art": {
                    "thumb": (
                        "http://127.0.0.1:57342/picture/server-1/"
                        "p-10-0-p-episode-current"
                    ),
                    "tvshow.clearart": "",
                    "tvshow.clearlogo": (
                        "http://127.0.0.1:57342/picture/server-1/"
                        "p-series-1-0-l-series-logo"
                    ),
                    "tvshow.fanart": (
                        "http://127.0.0.1:57342/picture/server-1/"
                        "p-series-1-0-B-series-fanart"
                    ),
                    "tvshow.landscape": (
                        "http://127.0.0.1:57342/picture/server-1/"
                        "p-series-1-0-t-series-landscape"
                    ),
                    "tvshow.poster": (
                        "http://127.0.0.1:57342/picture/server-1/"
                        "p-series-1-0-p-series-poster"
                    ),
                },
                "season": 1,
                "episode": 1,
                "showtitle": "Example Show",
                "plot": "Current plot",
                "playcount": 2,
                "rating": 8.5,
                "firstaired": "2025-01-01",
                "runtime": 1800,
            },
        )
        self.assertEqual(
            payload["play_url"],
            "plugin://plugin.service.emby-next-gen/"
            "?mode=play&server=server-1&item=11",
        )
        serialized = json.dumps(payload)
        self.assertNotIn("secret-token", serialized)
        self.assertNotIn("secret-device", serialized)
        self.assertNotIn("emby.example", serialized)

    def test_rejects_unsafe_server_and_item_ids_before_emitting_urls(self):
        unsafe_ids = (
            "11&mode=nodesreset",
            "11=nodesreset",
            "11%26mode%3Dnodesreset",
            "11?mode=nodesreset",
            "11/mode",
            "11\\mode",
            "11\r\nmode",
        )

        for unsafe_id in unsafe_ids:
            with self.subTest(identifier=unsafe_id, location="item"):
                current = episode(10, 1, 1)
                following = episode(unsafe_id, 1, 2)
                server = FakeServer(current, [current, following])
                xbmc.executeJSONRPC.reset_mock()

                self.assertFalse(upnext.send_upnext(server, "10", 0, 0))
                xbmc.executeJSONRPC.assert_not_called()
                self.assertEqual(upnext._picture("server-1", unsafe_id, "p", "tag"), "")

            with self.subTest(identifier=unsafe_id, location="server"):
                current = episode(10, 1, 1)
                following = episode(11, 1, 2)
                server = FakeServer(current, [current, following])
                server.ServerData["ServerId"] = unsafe_id
                xbmc.executeJSONRPC.reset_mock()

                self.assertFalse(upnext.send_upnext(server, "10", 0, 0))
                xbmc.executeJSONRPC.assert_not_called()
                self.assertEqual(upnext._picture(unsafe_id, "11", "p", "tag"), "")

    def test_supports_numeric_guid_and_established_server_ids(self):
        valid_pairs = (
            ("2a38697ffc1b428b943aa1b6014e2263", "58574"),
            (
                "2a38697f-fc1b-428b-943a-a1b6014e2263",
                "58575",
            ),
        )

        for server_id, item_id in valid_pairs:
            with self.subTest(server_id=server_id, item_id=item_id):
                current = episode(10, 1, 1)
                following = episode(item_id, 1, 2)
                server = FakeServer(current, [current, following])
                server.ServerData["ServerId"] = server_id
                xbmc.executeJSONRPC.reset_mock()

                self.assertTrue(upnext.send_upnext(server, "10", 0, 0))

                _, payload = self.decoded_signal()
                self.assertEqual(
                    payload["play_url"],
                    "plugin://plugin.service.emby-next-gen/"
                    f"?mode=play&server={server_id}&item={item_id}",
                )

    def test_selects_first_episode_of_next_season_in_server_order(self):
        current = episode(20, 1, 10)
        following = episode(21, 2, 1)
        server = FakeServer(current, [episode(19, 1, 9), current, following])

        self.assertTrue(upnext.send_upnext(server, "20", 0, 0))

        _, payload = self.decoded_signal()
        self.assertEqual(payload["next_episode"]["episodeid"], "21")
        self.assertEqual(server.API.get_episodes_calls, [("series-1", "20")])
        self.assertEqual(server.API.get_items_calls, [])

    def test_selects_special_from_server_defined_aired_order(self):
        current = episode(10, 1, 1)
        special = episode(
            15,
            0,
            0,
            AirsBeforeSeasonNumber=1,
            AirsBeforeEpisodeNumber=2,
        )
        server = FakeServer(current, [current, special, episode(11, 1, 2)])

        self.assertTrue(upnext.send_upnext(server, "10", 0, 0))

        _, payload = self.decoded_signal()
        self.assertEqual(payload["next_episode"]["episodeid"], "15")
        self.assertEqual(server.API.get_episodes_calls, [("series-1", "10")])
        self.assertEqual(server.API.get_items_calls, [])

    def test_preserves_server_order_when_episode_indexes_are_missing(self):
        current = episode(20, None, None, Name="Unnumbered episode")
        following = episode(21, None, None, Name="Next unnumbered episode")
        server = FakeServer(current, [current, following])

        self.assertTrue(upnext.send_upnext(server, "20", 0, 0))

        _, payload = self.decoded_signal()
        self.assertEqual(payload["next_episode"]["episodeid"], "21")
        self.assertEqual(server.API.get_episodes_calls, [("series-1", "20")])
        self.assertEqual(server.API.get_items_calls, [])

    def test_selects_server_ordered_second_part_with_duplicate_episode_number(self):
        current = episode(30, 1, 2, Name="Episode 2, part one")
        following = episode(31, 1, 2, Name="Episode 2, part two")
        server = FakeServer(current, [current, following, episode(32, 1, 3)])

        self.assertTrue(upnext.send_upnext(server, "30", 0, 0))

        _, payload = self.decoded_signal()
        self.assertEqual(payload["next_episode"]["episodeid"], "31")
        self.assertEqual(server.API.get_episodes_calls, [("series-1", "30")])
        self.assertEqual(server.API.get_items_calls, [])

    def test_does_not_signal_for_non_episode(self):
        current = {"Id": "movie-1", "Type": "Movie", "SeriesId": "series-1"}
        server = FakeServer(current, [current, episode(2, 1, 2)])

        self.assertFalse(upnext.send_upnext(server, "movie-1", 0, 0))

        xbmc.executeJSONRPC.assert_not_called()
        self.assertEqual(server.API.get_items_calls, [])

    def test_does_not_signal_when_current_episode_is_missing(self):
        server = FakeServer({}, [])

        self.assertFalse(upnext.send_upnext(server, "missing", 0, 0))

        xbmc.executeJSONRPC.assert_not_called()

    def test_does_not_signal_for_last_episode(self):
        current = episode(30, 3, 8)
        server = FakeServer(current, [episode(29, 3, 7), current])

        self.assertFalse(upnext.send_upnext(server, "30", 0, 0))

        xbmc.executeJSONRPC.assert_not_called()

    def test_metadata_and_artwork_use_safe_defaults(self):
        current = {"Id": "40", "Type": "Episode", "SeriesId": "series-1"}
        following = {"Id": "41", "Type": "Episode", "SeriesId": "series-1"}
        server = FakeServer(current, [current, following])

        self.assertTrue(upnext.send_upnext(server, "40", 0, 0))

        _, payload = self.decoded_signal()
        expected = {
            "episodeid": "40",
            "tvshowid": "series-1",
            "title": "",
            "art": {
                "thumb": "",
                "tvshow.clearart": "",
                "tvshow.clearlogo": "",
                "tvshow.fanart": "",
                "tvshow.landscape": "",
                "tvshow.poster": "",
            },
            "season": 0,
            "episode": 0,
            "showtitle": "",
            "plot": "",
            "playcount": 0,
            "rating": 0,
            "firstaired": "",
            "runtime": 0,
        }
        self.assertEqual(payload["current_episode"], expected)

    def test_includes_notification_time_from_valid_emby_ticks(self):
        current = episode(50, 1, 1)
        following = episode(51, 1, 2)
        server = FakeServer(current, [current, following])

        self.assertTrue(
            upnext.send_upnext(
                server,
                "50",
                1_800 * 10_000_000,
                1_740 * 10_000_000,
            )
        )

        _, payload = self.decoded_signal()
        self.assertEqual(payload["notification_time"], 60)

    def test_omits_notification_time_for_invalid_ticks(self):
        invalid_values = (
            (0, 100),
            (100, 0),
            (100, 100),
            (100, 101),
            (-100, 50),
            ("invalid", 50),
            (100, "invalid"),
            (None, None),
        )

        for runtime_ticks, credits_ticks in invalid_values:
            with self.subTest(runtime_ticks=runtime_ticks, credits_ticks=credits_ticks):
                current = episode(60, 1, 1)
                following = episode(61, 1, 2)
                server = FakeServer(current, [current, following])
                xbmc.executeJSONRPC.reset_mock()

                self.assertTrue(
                    upnext.send_upnext(
                        server,
                        "60",
                        runtime_ticks,
                        credits_ticks,
                    )
                )

                _, payload = self.decoded_signal()
                self.assertNotIn("notification_time", payload)

    def test_dispatches_episode_lookup_on_thread_only_when_enabled(self):
        playing_item = [
            {"ItemId": "70", "RunTimeTicks": 1_800 * 10_000_000},
            0,
            0,
            1_740 * 10_000_000,
            object(),
            1,
            "episode",
            "",
        ]

        upnext.dispatch(playing_item)

        xbmc.getCondVisibility.assert_called_once_with(
            "System.AddonIsEnabled(service.upnext)"
        )
        utils.start_thread.assert_called_once_with(
            upnext.send_upnext,
            (
                playing_item[4],
                "70",
                1_800 * 10_000_000,
                1_740 * 10_000_000,
            ),
        )

        for enabled, media_type in ((False, "episode"), (True, "movie")):
            with self.subTest(enabled=enabled, media_type=media_type):
                xbmc.getCondVisibility.reset_mock()
                xbmc.getCondVisibility.return_value = enabled
                utils.start_thread.reset_mock()
                playing_item[6] = media_type

                upnext.dispatch(playing_item)

                utils.start_thread.assert_not_called()


if __name__ == "__main__":
    unittest.main()

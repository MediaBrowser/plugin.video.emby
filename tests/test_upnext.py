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

    def get_Item(self, *args):
        self.get_item_calls.append(args)
        return self.current

    def get_Items(self, *args):
        self.get_items_calls.append(args)
        return iter(self.episodes)


class FakeServer:
    def __init__(self, current, episodes):
        self.API = FakeAPI(current, episodes)
        self.ServerData = {
            "ServerId": "server-1",
            "ServerUrl": "https://emby.example",
            "AccessToken": "secret-token",
            "DeviceId": "secret-device",
        }


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

    def test_selects_first_episode_of_next_season_in_explicit_series_order(self):
        current = episode(20, 1, 10)
        following = episode(21, 2, 1)
        server = FakeServer(current, [episode(19, 1, 9), current, following])

        self.assertTrue(upnext.send_upnext(server, "20", 0, 0))

        _, payload = self.decoded_signal()
        self.assertEqual(payload["next_episode"]["episodeid"], "21")
        args = server.API.get_items_calls[0]
        self.assertEqual(args[0:3], ("series-1", ("Episode",), False))
        self.assertEqual(args[3]["SortOrder"], "Ascending")
        self.assertEqual(
            args[3]["SortBy"],
            "ParentIndexNumber,IndexNumber,SortName",
        )

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

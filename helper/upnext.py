import base64
import json
import math

import xbmc

from helper import utils


ADDON_ENABLED = "System.AddonIsEnabled(service.upnext)"
ART_TEMPLATE = "http://127.0.0.1:57342/picture/{}/p-{}-0-{}-{}"


def dispatch(playing_item):
    if len(playing_item) < 7 or str(playing_item[6]).lower() != "episode":
        return

    if not xbmc.getCondVisibility(ADDON_ENABLED):
        return

    session_data = playing_item[0]
    server = playing_item[4]

    if not session_data or not server or not session_data.get("ItemId"):
        return

    utils.start_thread(
        send_upnext,
        (
            server,
            session_data["ItemId"],
            session_data.get("RunTimeTicks"),
            playing_item[3],
        ),
    )


def send_upnext(server, item_id, runtime_ticks, credits_ticks):
    try:
        return _send_upnext(server, item_id, runtime_ticks, credits_ticks)
    except Exception:
        xbmc.log("EMBY.helper.upnext: Up Next integration failed", 2)
        return False


def _send_upnext(server, item_id, runtime_ticks, credits_ticks):
    current = server.API.get_Item(item_id, ("Episode",), True, False, True)

    if current.get("Type") != "Episode" or not current.get("SeriesId"):
        return False

    episodes = server.API.get_Items(
        current["SeriesId"],
        ("Episode",),
        False,
        {
            "SortBy": "ParentIndexNumber,IndexNumber,SortName",
            "SortOrder": "Ascending",
        },
        "",
        None,
        True,
    )
    following = _following_episode(episodes, current.get("Id"))

    if not following:
        return False

    server_id = server.ServerData["ServerId"]
    payload = {
        "current_episode": _episode_info(current, server_id),
        "next_episode": _episode_info(following, server_id),
        "play_url": (
            "plugin://plugin.service.emby-next-gen/"
            f"?mode=play&server={server_id}&item={following.get('Id', '')}"
        ),
    }
    notification_time = _notification_time(runtime_ticks, credits_ticks)

    if notification_time is not None:
        payload["notification_time"] = notification_time

    encoded_payload = base64.b64encode(
        json.dumps(payload).encode("utf-8")
    ).decode("ascii")
    xbmc.executeJSONRPC(
        json.dumps(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "JSONRPC.NotifyAll",
                "params": {
                    "sender": "plugin.service.emby-next-gen.SIGNAL",
                    "message": "upnext_data",
                    "data": [encoded_payload],
                },
            }
        )
    )
    return True


def _following_episode(episodes, current_id):
    current_found = False

    for item in episodes:
        if current_found:
            return item

        if str(item.get("Id")) == str(current_id):
            current_found = True

    return None


def _episode_info(item, server_id):
    user_data = item.get("UserData")

    if not isinstance(user_data, dict):
        user_data = {}

    return {
        "episodeid": item.get("Id", ""),
        "tvshowid": item.get("SeriesId", ""),
        "title": _text(item.get("Name")),
        "art": _art(item, server_id),
        "season": _integer(item.get("ParentIndexNumber")),
        "episode": _integer(item.get("IndexNumber")),
        "showtitle": _text(item.get("SeriesName")),
        "plot": _text(item.get("Overview")),
        "playcount": _integer(user_data.get("PlayCount")),
        "rating": _number(item.get("CommunityRating")),
        "firstaired": _text(item.get("PremiereDate")),
        "runtime": _runtime(item.get("RunTimeTicks")),
    }


def _art(item, server_id):
    art = {
        "thumb": "",
        "tvshow.clearart": "",
        "tvshow.clearlogo": "",
        "tvshow.fanart": "",
        "tvshow.landscape": "",
        "tvshow.poster": "",
    }
    image_tags = item.get("ImageTags")

    if not isinstance(image_tags, dict):
        image_tags = {}

    if _valid_tag(image_tags.get("Primary")):
        art["thumb"] = _picture(server_id, item.get("Id"), "p", image_tags["Primary"])
    elif _valid_tag(image_tags.get("Thumb")):
        art["thumb"] = _picture(server_id, item.get("Id"), "t", image_tags["Thumb"])

    inherited_art = (
        ("tvshow.clearart", "ParentArtItemId", "ParentArtImageTag", "a"),
        ("tvshow.clearlogo", "ParentLogoItemId", "ParentLogoImageTag", "l"),
        ("tvshow.landscape", "ParentThumbItemId", "ParentThumbImageTag", "t"),
        ("tvshow.poster", "SeriesId", "SeriesPrimaryImageTag", "p"),
    )

    for art_key, item_key, tag_key, art_kind in inherited_art:
        tag = item.get(tag_key)

        if _valid_tag(tag):
            art[art_key] = _picture(server_id, item.get(item_key), art_kind, tag)

    backdrop_tags = item.get("ParentBackdropImageTags")

    if isinstance(backdrop_tags, (list, tuple)) and backdrop_tags:
        if _valid_tag(backdrop_tags[0]):
            art["tvshow.fanart"] = _picture(
                server_id,
                item.get("ParentBackdropItemId"),
                "B",
                backdrop_tags[0],
            )

    return art


def _picture(server_id, item_id, art_kind, image_tag):
    if not server_id or not item_id or not _valid_tag(image_tag):
        return ""

    return ART_TEMPLATE.format(server_id, item_id, art_kind, image_tag)


def _valid_tag(value):
    return bool(value and value != "None")


def _text(value):
    return value if isinstance(value, str) else ""


def _number(value):
    if isinstance(value, bool):
        return 0

    try:
        value = float(value)
    except (TypeError, ValueError):
        return 0

    if not math.isfinite(value):
        return 0

    if value.is_integer():
        return int(value)

    return value


def _integer(value):
    return int(_number(value))


def _runtime(runtime_ticks):
    runtime_ticks = _number(runtime_ticks)

    if runtime_ticks <= 0:
        return 0

    return int(runtime_ticks / 10_000_000)


def _notification_time(runtime_ticks, credits_ticks):
    runtime_ticks = _number(runtime_ticks)
    credits_ticks = _number(credits_ticks)

    if runtime_ticks <= 0 or credits_ticks <= 0 or credits_ticks >= runtime_ticks:
        return None

    seconds = (runtime_ticks - credits_ticks) / 10_000_000

    if seconds <= 0:
        return None

    if seconds.is_integer():
        return int(seconds)

    return seconds

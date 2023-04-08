import xbmc
from helper import utils

if utils.KodiMajorVersion == "19":
    from . import listitem_kodi19 as listitem_kodiversion
else:
    from . import listitem_kodi20 as listitem_kodiversion

def get_shortdate(EmbyDate):
    try:
        DateTime = EmbyDate.split(" ")
        DateTemp = DateTime[0].split("-")
        return f"{DateTemp[2]}-{DateTemp[1]}-{DateTemp[0]}"
    except Exception as Error:
        xbmc.log(f"EMBY.emby.listitem: No valid date: {EmbyDate} / {Error}", 0) # LOGDEBUG
        return ""

def set_ListItem_from_Kodi_database(KodiItem, Path=None):
    return listitem_kodiversion.set_ListItem_from_Kodi_database(KodiItem, Path)

def set_ListItem(item, server_id, Path=None):
    return listitem_kodiversion.set_ListItem(item, server_id, Path, get_shortdate)

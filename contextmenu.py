# -*- coding: utf-8 -*-

#################################################################################################

import logging
import os
import sys

import xbmc
import xbmcaddon
import xbmcgui

#################################################################################################

_ADDON = xbmcaddon.Addon(id='plugin.video.emby')
_CWD = _ADDON.getAddonInfo('path').decode('utf-8')
_BASE_LIB = xbmc.translatePath(os.path.join(_CWD, 'resources', 'lib')).decode('utf-8')
sys.path.append(_BASE_LIB)

#################################################################################################

import api
import loghandler
import read_embyserver as embyserver
import embydb_functions as embydb
import musicutils as musicutils
from utils import settings, dialog, language as lang, kodiSQL

#################################################################################################

loghandler.config()
log = logging.getLogger("EMBY.contextmenu")

#################################################################################################

OPTIONS = {
    
    'Refresh': lang(30410),
    'Delete': lang(30409),
    'Addon': lang(30408),
    'AddFav': lang(30405),
    'RemoveFav': lang(30406),
    'RateSong': lang(30407)
}

# Kodi contextmenu item to configure the emby settings
if __name__ == '__main__':

    kodi_id = xbmc.getInfoLabel('ListItem.DBID').decode('utf-8')
    item_type = xbmc.getInfoLabel('ListItem.DBTYPE').decode('utf-8')
    item_id = xbmc.getInfoLabel('ListItem.Property(embyid)')

    if not item_type:

        if xbmc.getCondVisibility("Container.Content(albums)"):
            item_type = "album"
        elif xbmc.getCondVisibility("Container.Content(artists)"):
            item_type = "artist"
        elif xbmc.getCondVisibility("Container.Content(songs)"):
            item_type = "song"
        elif xbmc.getCondVisibility("Container.Content(pictures)"):
            item_type = "picture"
        else:
            log.info("item_type is unknown")

    if not item_id and kodi_id and item_type:
        conn = kodiSQL('emby')
        cursor = conn.cursor()
        emby_db = embydb.Embydb_Functions(cursor)
        item = emby_db.getItem_byKodiId(kodi_id, item_type)
        cursor.close()
        try:
            item_id = item[0]
        except TypeError:
            pass

    log.info("Found item_id: %s item_type: %s", item_id, item_type)
    if item_id:

        emby = embyserver.Read_EmbyServer()
        item = emby.getItem(item_id)
        API = api.API(item)
        userdata = API.getUserData()
        likes = userdata['Likes']
        favourite = userdata['Favorite']

        options = []

        if favourite:
            # Remove from emby favourites
            options.append(OPTIONS['RemoveFav'])
        else:
            # Add to emby favourites
            options.append(OPTIONS['AddFav']) 

        if item_type == "song":
            # Set custom song rating
            options.append(OPTIONS['RateSong'])

        # Refresh item
        options.append(OPTIONS['Refresh'])
        # Delete item
        options.append(OPTIONS['Delete'])
        # Addon settings
        options.append(OPTIONS['Addon'])

        # Display select dialog and process results
        resp = dialog(type_="select", heading=lang(30401), list=options)
        if resp > -1:
            selected = options[resp]

            if selected == OPTIONS['Refresh']:
                emby.refreshItem(item_id)

            elif selected == OPTIONS['AddFav']:
                emby.updateUserRating(item_id, favourite=True)

            elif selected == OPTIONS['RemoveFav']:
                emby.updateUserRating(item_id, favourite=False)

            elif selected == OPTIONS['RateSong']:

                conn = kodiSQL('music')
                cursor = conn.cursor()
                query = "SELECT rating FROM song WHERE idSong = ?"
                cursor.execute(query, (kodi_id,))
                try:
                    value = cursor.fetchone()[0]
                    current_value = int(round(float(value),0))
                except TypeError:
                    pass
                else:
                    new_value = dialog.numeric(0, lang(30411), str(current_value))
                    if new_value > -1:
                        
                        new_value = int(new_value)
                        if new_value > 5:
                            new_value = 5

                        if settings('enableUpdateSongRating') == "true":
                            musicutils.updateRatingToFile(new_value, API.getFilePath())

                        query = "UPDATE song SET rating = ? WHERE idSong = ?"
                        cursor.execute(query, (new_value, kodi_id,))
                        conn.commit()
                        
                        '''if settings('enableExportSongRating') == "true":
                            like, favourite, deletelike = musicutils.getEmbyRatingFromKodiRating(new_value)
                            emby.updateUserRating(item_id, like, favourite, deletelike)'''
                finally:
                    cursor.close()

            elif selected == OPTIONS['Addon']:
                xbmc.executebuiltin('Addon.OpenSettings(plugin.video.emby)')

            elif selected == OPTIONS['Delete']:

                delete = True
                if settings('skipContextMenu') != "true":

                    if not dialog(type_="yesno", heading="{emby}", line1=lang(33041)):
                        log.info("User skipped deletion for: %s", item_id)
                        delete = False

                if delete:
                    log.info("Deleting request: %s", item_id)
                    emby.deleteItem(item_id)

            xbmc.sleep(500)
            xbmc.executebuiltin('Container.Refresh')

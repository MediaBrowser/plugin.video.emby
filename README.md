### Welcome to PlexKodiConnect
**Connect your Plex Media Server to a Kodi Front End**

PlexKodiConnect combines the best of Kodi - ultra smooth navigation, beautiful UIs and playback of any file under the sun, and Plex to manage all your media without lifting a finger.


**What does it do?**

With other addons for Kodi there are a couple of issues:
- 3rd party addons such as NextAired, remote apps etc. won't work
- Slow speed: when browsing the data has to be retrieved from the server. Especially on slower devices this can take too much time.
- You can only use special Kodi skins
- All kinds of workarounds are needed to get the best experience on Kodi clients

This addon synchronizes your media on your Plex server to the native Kodi database. Because we use the native Kodi database with this new approach the above limitations are gone! 
- You can browse your media full speed, e.g. images are cached
- All other Kodi addons will be able to "see" your media, thinking it's normal Kodi stuff
- Use any Kodi skin you want!


**Installation in Kodi**

1. Uninstall everything else Plex related first, e.g. PlexBMC and PlexBMC Helper. 
2. Simply fire up Kodi and "Install from ZIP" from here on. 
3. Install the 2 needed dependencies first (be sure to NOT download the sources but the additional release files): https://github.com/croneter/plugin.video.plexkodiconnect.tvshows/releases/ and https://github.com/croneter/plugin.video.plexkodiconnect.movies/releases/
4. Then install PlexKodiConnect, again the additional release file from here: https://github.com/croneter/PlexKodiConnect/releases/
5. Within a few seconds you should be prompted to log into plex.tv. This is mandatory for Plex Home, otherwise you can skip. If nothing happens, try to restart Kodi
6. Once you have succesfully authenticated, the initial sync will start. 
7. The first sync of the Plex server to local Kodi database may take a **LONG time**. With my setup (~400 movies, ~600 episodes, couple of Test music albums and a very powerful NAS), sync takes approximately 5 minutes.
8. Once the full sync is done, you can browse your media in Kodi, syncs will be automatically done in the background.
9. Restart Kodi, just to be on the safe side

This software is yet in a Beta version. You have been warned. It's very probable that you will need to fully resync and reset your setup on a regular basis.


**Having Problems? Then thanks for your log files**

First try to restart Kodi. If that does not help: try resetting the Addon: Settings -> Advanced -> "Partial or Full Reset of Database and PKC". Then choose 3x "Yes".
If you're still having problems, let me know:

1. Activate a more detailed logging for KodiPlexConnect: Settings -> Advanced -> "Debug"
2. Follow the instructions here: http://kodi.wiki/view/Log_file/Easy and try to reproduce the bug
3. Don't forget to **delete all references to any of your Plex tokens**!! You don't want others to have access to your Plex installation
4. Post the link to your log (that you posted e.g. here: http://xbmclogs.com/) on https://forums.plex.tv/discussion/210023/plexkodiconnect-supercharge-your-plex-kodi-connection (or send a private message to prevent your Plex keys from leaking)


**What is currently supported ?**

Currently these features are working:
- Movies
- TV Shows
- Full sync at first run, then periodic delta syncs every 30min (customizable)
- Instant watched state/resume status sync: This is a 2-way synchronisation. Any watched state or resume status will be instantly (within seconds) reflected to or from Kodi and the server
- Plex Companion: fling Plex media (or anything else) from other Plex devices to PlexKodiConnect
- Play directly from network paths (e.g. "\\\\server\\Plex\\movie.mkv" or "smb://server/Plex/movie.mkv") instead of slow HTTP (e.g. "192.168.1.1:32400"). You have to setup all your Plex libraries to point to such network paths


**Known Issues:**

Solutions are unlikely due to the nature of these issues
- *Plex Music:* Kodi tries to scan every(!) single Plex song on startup. This leads to errors in the Kodi log file and potentially even crashes. (Plex puts each song in a "dedicated folder", e.g. 'http://192.168.1.1:32400/library/parts/749450/'. Kodi unsuccessfully tries to scan these folders)
- *Plex Music:* You must have a static IP address for your Plex media server if you plan to use Plex Music features. This is due to the way Kodi works and cannot be helped. 
- If something on the PMS has changed, this change is synced to Kodi. Hence if you rescan your entire library, a long PlexKodiConnect re-sync is triggered.
- External Plex subtitles (separate file, e.g. mymovie.srt) can be used, but it is impossible to label them correctly/tell what language they are in. However, this is not the case if you use direct paths

*Background Sync:*
The Plex Server does not tell anyone of the following changes. Hence PKC cannot detect these changes instantly but will notice them on full/delta syncs. 
- Toggle the viewstate of an item to (un)watched outside of Kodi
- Changing details of an item, e.g. replacing a poster
However, some changes to individual items are instantly detected, e.g. if you match a yet unrecognized movie. 


**Known Bugs:**
- Plex Music for direct paths does not work yet. Items on Kodi get deleted  instantly.


**What could be in the pipeline for future development?**
- Watch Later
- Playlists
- Homevideos
- Pictures
- Music Videos
- Automatic updates
- Simultaneously connecting to several PMS
- TV Shows Theme Music (ultra-low prio)


**Important note about MySQL database in kodi**

The addon is not (and will not be) compatible with the MySQL database replacement in Kodi. In fact, PlexKodiConnect takes over the point of having a MySQL database because it acts as a "man in the middle" for your entire media library.

**Important note about user collections/nodes**

Plex has the ability to create custom libraries for your Media, such as having a separate folder for your "Kids Movies" etc. In Kodi this isn't supported, you just have "movies" or "tvshows". But... Kodi let's you create your own playlists and tags to get this same experience. During the sync the foldernode from the Plex server is added to the movies that are imported. In Kodi you can browse to Movie library --> tags and you will have a filtered result that points at your custom node. If you have a skin that let's you create any kind of shortcut on the homescreen you can simply create a shortcut to that tag. Another possibility is to create a "smart playlist" with Kodi and set it to show the content of a certain tag. 

**Credits**
- PlexKodiConnect shamelessly uses pretty much all the code of "Emby for Kodi" by the awesome Emby team (see https://github.com/MediaBrowser/plugin.video.emby). Thanks for sharing guys!!
- Plex Companion ("PlexBMC Helper") and other stuff was adapted from @Hippojay 's great work (see https://github.com/hippojay).
- The foundation of the Plex API is all iBaa's work (https://github.com/iBaa/PlexConnect).
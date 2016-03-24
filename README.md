**Credits**
- PlexKodiConnect shamelessly uses pretty much all the code of "Emby for Kodi" by the awesome Emby team (see https://github.com/MediaBrowser/plugin.video.emby). Thanks for sharing guys!!
- Plex Companion ("PlexBMC Helper") and other stuff was adapted from @Hippojay 's great work (see https://github.com/hippojay).
- The foundation of the Plex API is all iBaa's work (https://github.com/iBaa/PlexConnect).

**Installation in Kodi**

1. You might want to uninstall everything else Plex related first, e.g. PlexBMC and PlexBMC Helper. Starting with a fresh Kodi install might be a good idea. Be sure to use a "normal", unmodded Skin in Kodi to start with.
If you're updating, you might also want to do a complete reset of the plugin: Settings -> Advanced -> "Perform local database reset (full resync)". Choose "Yes" for all questions.
2. Simply fire up Kodi and Install from ZIP from here on. 
3. Install the 2 needed dependencies first (be sure to NOT download the sources but the additional release files): https://github.com/croneter/plugin.video.plexkodiconnect.tvshows/releases/ and https://github.com/croneter/plugin.video.plexkodiconnect.movies/releases/
5. Then install PlexKodiConnect, again the additional release file from here: https://github.com/croneter/PlexKodiConnect/releases/
6. Within a few seconds you should be prompted to log into plex.tv. This is mandatory for Plex Home, otherwise you can skip. If nothing happens, try to restart Kodi
7. Once you're succesfully authenticated to your Plex server, the initial sync will start. 
8. The first sync of the Plex server to local Kodi database may take a LONG time. With my setup (~400 movies, ~600 episodes, couple of Test music albums and a very powerful NAS), sync takes approximately 5 minutes.
9. Once the full sync is done, you can browse your media in Kodi, syncs will be automatically done in the background.
10. Restart Kodi!

This software is yet in a Beta version. You have been warned. It's very probable that you will need to fully resync and reset your setup on a regular basis.

**Having Problems? Then thanks for your log files**
It's always a good idea to try resetting the Addon: Settings -> Advanced -> "Perform local database reset (full resync)"
1. Activate a more detailed logging for KodiPlexConnect: Settings -> Advanced -> "Debug"
2. Follow the instructions here: http://kodi.wiki/view/Log_file/Easy
3. Don't forget to delete all references to any of your Plex tokens!! You don't want others to have access to your Plex installation
4. Post the link to your log (that you posted e.g. here: http://xbmclogs.com/) on https://forums.plex.tv/discussion/210023/plexkodiconnect-supercharge-your-plex-kodi-connection (or send a private message)


### Welcome to PlexKodiConnect
**Connect your Plex Media Server to a Kodi Front End**

PlexKodiConnect combines the best of Kodi - ultra smooth navigation, beautiful UIs and playback of any file under the sun, and Plex.

**What does it do?**

With other addons for Kodi there are a couple of issues:
- 3rd party addons such as NextAired, remote apps etc. won't work
- Speed: when browsing the data has to be retrieved from the server. Especially on slower devices this can take too much time.
- You can only use special Kodi skins
- All kinds of workaround were needed to get the best experience on Kodi clients

This addon synchronizes your media on your Plex server to the native Kodi database. Because we use the native Kodi database with this new approach the above limitations are gone! 
- You can browse your media full speed
- All other Kodi addons will be able to "see" your media, thinking it's normal Kodi stuff
- Use any Kodi skin you want!

**What is currently supported ?**

Currently these features are working:
- Movies
- TV Shows
- Full sync at first run (import), background syncs configurable by the user in the addonsetting. The current default is that it will do a full sync on the background approximately every 30min and continuous incremential syncs.
- Watched state/resume status sync: This is a 2-way synchronisation. Any watched state or resume status will be instantly (within seconds) reflected to or from Kodi and the server.
- Plex Companion: you can fling Plex media from other Plex devices to PlexKodiConnect
- Play directly from network paths (e.g. "\\\\server\\Plex\\movie.mkv" on Windows or SMB paths "smb://server/Plex/movie.mkv") instead of slow HTTP (e.g. "192.168.1.1:32400"). You have to setup all your Plex libraries to point to such network paths. 


**Known "Larger" Issues:**

Solutions are unlikely due to the nature of these issues
- **Plex Music:** You must have a static IP address for your Plex media server if you plan to use Plex Music features. This is due to the way Kodi works and cannot be helped. 
- **Plex Music:** Kodi tries to scan every(!) single Plex song on startup. This leads to errors in the Kodi log file and potentially even crashes. (Plex puts each song in a "dedicated folder", e.g. 'http://192.168.1.1:32400/library/parts/749450/'. Kodi unsuccessfully tries to scan these folders)
- **Plex updates:** PlexKodiConnect continuously polls the Plex Media Server for changes. If something on the PMS has changed, this change is synced to Kodi. Hence if you rescan your entire library, a long PlexKodiConnect re-sync is triggered.
- **Subtitles**: external Plex subtitles (separate file, e.g. mymovie.srt) can be used, but it is impossible to label them correctly/tell what language they are in
- **Direct Paths:** If you use direct paths, your (initial) sync will be slower

**Known Bugs:**
- **Plex Music:** Plex Music for direct paths does not work yet.
- **Video Nodes**: some nodes, e.g. "On Deck", are customized/hacked. Hence no access to movie metadata is possible, because Kodi does not know it's a library item


**What could be in the pipeline for future development?**
- Watch Later
- Playlists
- Homevideos
- Pictures
- Music Videos
- Automatic updates
- Redesigned background sync process that puts less strain on the PMS
- Simultaneously connecting to several PMS
- TV Shows Theme Music (ultra-low prio)



**Important note about MySQL database in kodi**

The addon is not (and will not be) compatible with the MySQL database replacement in Kodi. In fact, PlexKodiConnect takes over the point of having a MySQL database because it acts as a "man in the middle" for your entire media library.

**Important note about user collections/nodes**

Plex has the ability to create custom libraries for your Media, such as having a separate folder for your "Kids Movies" etc. In Kodi this isn't supported, you just have "movies" or "tvshows". But... Kodi let's you create your own playlists and tags to get this same experience. During the sync the foldernode from the Plex server is added to the movies that are imported. In Kodi you can browse to Movie library --> tags and you will have a filtered result that points at your custom node. If you have a skin that let's you create any kind of shortcut on the homescreen you can simply create a shortcut to that tag. Another possibility is to create a "smart playlist" with Kodi and set it to show the content of a certain tag. 

Report bugs or pictures of your burning raspi on the forums 

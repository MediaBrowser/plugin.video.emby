### This is an early BETA Version, so Beware of the Dragons
**Credits**
- PlexKodiConnect shamelessly uses pretty much all the code of "Emby for Kodi" by the awesome Emby team (see https://github.com/MediaBrowser/plugin.video.emby). Thanks for sharing guys!!
- Plex Companion ("PlexBMC Helper") and other stuff was adapted from Hippojay's great work (see https://github.com/hippojay).
- The foundation of the Plex API is all iBaa's work (https://github.com/iBaa/PlexConnect).

**Installation in Kodi**

1. You might want to uninstall everything else Plex related first, e.g. PlexBMC and PlexBMC Helper. Starting with a fresh Kodi install might be a good idea. Be sure to use a "normal", unmodded Skin in Kodi
2. Simply fire up Kodi and Install from ZIP from here on. 
3. Install the 2 needed dependencies first (be sure to NOT download the sources but the additional release files): https://github.com/croneter/plugin.video.plexkodiconnect.tvshows/releases/tag/1.0.0 and https://github.com/croneter/plugin.video.plexkodiconnect.movies/releases/tag/1.0.0
5. Then install PlexKodiConnect, again the additional release file from here.
6. Within a few seconds you should be prompted to log into plex.tv. This is mandatory for Plex Home, otherwise you can skip. If nothing happens, try to restart Kodi
7. Once you're succesfully authenticated to your Plex server, the initial sync will start. 
8. The first sync of the Plex server to local Kodi database may take a LONG time. With my setup (~400 movies, ~600 episodes, couple of Test music albums and a very powerful NAS), sync take approximately 5 minutes.
9. Once the full sync is done, you can browse your media in Kodi, syncs will be automatically done in the background.

Again, this is beta. You have been warned. It's a given that you will need to fully resync and reset your setup on a regular basis.


### Welcome to PlexKodiConnect
**Connect your Plex Media Server to a Kodi Front End**

PlexKodiConnect combines the best of Kodi - ultra smooth navigation, beautiful UIs and playback of any file under the sun, and Plex.

**What does it do?**

With other addons for Kodi there are a couple of issues:
- 3rd party addons such as NextAired, remote apps etc. won't work
- Speed: when browsing the data has to be retrieved from the server. Especially on slower devices this can take too much time.
- All kinds of workaround were needed to get the best experience on Kodi clients

This addon synchronizes your media on your Plex server to the native Kodi database. Because we use the native Kodi database with this new approach the above limitations are gone! You can browse your media full speed and all other Kodi addons will be able to "see" your media.

**What is currently supported ?**

Guess what, this is BETA. Currently these features are working:
- Movies
- TV Shows
- Full sync at first run (import), background syncs configurable by the user in the addonsetting. The current default is that it will do a full sync on the background approximately every 30min and continuous incremential syncs.
- Watched state/resume status sync: This is a 2-way synchronisation. Any watched state or resume status will be instantly (within seconds) reflected to or from Kodi and the server.


**Known Issues:**
- Windows users: Kodi Helix 14.2 RC1 required - other versions will result in errors with recently added items etc.
- You must have a static IP address for your Plex media server if you plan to use Plex Music features. This is due to the way Kodi works and cannot be helped.
- This is a BETA version and could potentially set fire to your Raspi


**What could be in the pipeline?**
- Watch later
- MusicVideos
- TV Shows Theme Music (ultra-low prio)



**Important note about MySQL database in kodi**

The addon is not (and will not be) compatible with the MySQL database replacement in Kodi. In fact, PlexKodiConnect takes over the point of having a MySQL database because it acts as a "man in the middle" for your entire media library.

**Important note about user collections/nodes**

Plex has the ability to create custom libraries for your Media, such as having a separate folder for your "Kids Movies" etc. In Kodi this isn't supported, you just have "movies" or "tvshows". But... Kodi let's you create your own playlists and tags to get this same experience. During the sync the foldernode from the Plex server is added to the movies that are imported. In Kodi you can browse to Movie library --> tags and you will have a filtered result that points at your custom node. If you have a skin that let's you create any kind of shortcut on the homescreen you can simply create a shortcut to that tag. Another possibility is to create a "smart playlist" with Kodi and set it to show the content of a certain tag. 

Report bugs or pictures of your burning raspi on the forums 
